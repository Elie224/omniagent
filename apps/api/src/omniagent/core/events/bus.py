"""Bus evenementiel asynchrone interne (in-process).

Permet aux differents composants (agents, orchestrateur, connecteurs, memory) de
publier et de s abonner a des evenements metier.

Limitation : in-process. Pour du multi-pod, remplacer par Redis pub/sub ou Kafka.
"""
from __future__ import annotations
import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Awaitable, Callable
from uuid import uuid4


class EventType(str, Enum):
    AGENT_STARTED = "agent.started"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"
    TOOL_EXECUTED = "tool.executed"
    TOOL_FAILED = "tool.failed"
    MEMORY_UPDATED = "memory.updated"
    MEMORY_POISONED = "memory.poisoned"
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"
    WORKFLOW_ROLLED_BACK = "workflow.rolled_back"
    CONNECTOR_CALLED = "connector.called"
    CONNECTOR_FAILED = "connector.failed"
    QUOTA_EXCEEDED = "quota.exceeded"
    POLICY_DENIED = "policy.denied"
    NOTIFICATION_SENT = "notification.sent"


@dataclass
class Event:
    type: EventType
    payload: dict
    source: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_id: str = field(default_factory=lambda: str(uuid4()))
    correlation_id: str | None = None
    causation_id: str | None = None
    user_id: str | None = None
    # Versioning : permet de faire evoluer le payload d un type d event
    # sans casser les consommateurs. v1 = format initial. v2+ = format migre.
    # Voir core/events/schema.py pour le registre de migrations.
    schema_version: int = 1

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "type": self.type.value,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "user_id": self.user_id,
        }


SubscriberCallback = Callable[[Event], Awaitable[None]]


class EventBus:
    def __init__(self, history_limit: int = 1000, store=None,
                 dedupe_window: int = 0):
        """`store` est un EventStore optionnel (in-memory par defaut).

        Si fourni, chaque publish() est appende au store en plus de la fan-out
        aux subscribers. Le store devient la source de verite pour les queries
        long-terme ; `get_history` reste utile pour les snapshots recents en RAM.

        `dedupe_window` : si > 0, un publish() avec un event_id deja vu recemment
        est ignore (ni fan-out, ni store append, ni history). Protege des
        retries orchestrateur qui re-emettraient le meme event. 0 = desactive.
        """
        self._subscribers: dict[EventType, list[SubscriberCallback]] = defaultdict(list)
        self._history: list[Event] = []
        self._history_limit = history_limit
        self._lock = asyncio.Lock()
        self._dlq: list[Event] = []
        self._store = store
        self._tenant_context: dict[str, str | None] = {}
        self._dedupe_window = dedupe_window
        self._seen_event_ids: set[str] = set()

    def set_tenant_context(self, **kwargs) -> None:
        """Definit le tenant_id courant pour les events publies depuis ce bus.

        Cle supportee : tenant_id. Appele par le middleware auth pour propager
        le tenant sans modifier la signature de publish().
        """
        self._tenant_context.update(kwargs)

    def get_store(self):
        """Expose le store sous-jacent pour les queries (debug, dashboard)."""
        return self._store

    def subscribe(self, event_type: EventType,
                  callback: SubscriberCallback) -> Callable[[], None]:
        self._subscribers[event_type].append(callback)

        def unsubscribe() -> None:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)
        return unsubscribe

    async def publish(self, event: Event) -> int:
        # Validation optionnelle du payload contre le schema Pydantic du type.
        # Si invalide, on log un warning mais on ne casse pas la fan-out
        # (la detection de drift est un signal, pas un bloqueur).
        from omniagent.core.events.schema import validate_payload
        validated_payload, _ok = validate_payload(event.type.value, event.payload)
        # On ne mute pas l objet event (l appelant peut le reutiliser),
        # on travaille sur un clone leger pour la persistance.
        if validated_payload is not event.payload:
            event = Event(
                type=event.type, payload=validated_payload, source=event.source,
                timestamp=event.timestamp, event_id=event.event_id,
                correlation_id=event.correlation_id, causation_id=event.causation_id,
                user_id=event.user_id,
            )
        # Dedupe court-terme : si on a deja vu cet event_id recemment, on no-op
        # pour eviter qu un retry orchestrateur re-declenche la fan-out.
        if self._dedupe_window > 0 and event.event_id in self._seen_event_ids:
            return 0
        async with self._lock:
            self._history.append(event)
            if len(self._history) > self._history_limit:
                self._history.pop(0)
            if self._dedupe_window > 0:
                self._seen_event_ids.add(event.event_id)
                # GC : on garde au plus `dedupe_window` ids en memoire
                if len(self._seen_event_ids) > self._dedupe_window:
                    # Retirer la moitie (FIFO simple)
                    drop = list(self._seen_event_ids)[: self._dedupe_window // 2]
                    for eid in drop:
                        self._seen_event_ids.discard(eid)
        # Persistance append-only : best-effort, on n interrompt pas la fan-out
        # si le store est en erreur (l event reste dans l history RAM).
        if self._store is not None:
            try:
                await self._store.append(
                    event, tenant_id=self._tenant_context.get("tenant_id"),
                )
            except Exception as e:
                # Logue mais ne casse pas le flow metier.
                self._dlq.append(event)
                print(f"[EventBus] store.append failed for {event.type.value}: {e}")
        handlers = list(self._subscribers.get(event.type, []))
        success = 0
        for handler in handlers:
            try:
                await handler(event)
                success += 1
            except Exception as e:
                self._dlq.append(event)
                print(f"[EventBus] handler failed for {event.type.value}: {e}")
        return success

    def get_history(self, event_type: EventType | None = None,
                    limit: int = 100, user_id: str | None = None) -> list[dict]:
        events = self._history
        if event_type:
            events = [e for e in events if e.type == event_type]
        if user_id:
            events = [e for e in events if e.user_id == user_id]
        return [e.to_dict() for e in events[-limit:]]

    def get_dlq(self) -> list[dict]:
        return [e.to_dict() for e in self._dlq]

    def clear(self) -> None:
        self._history.clear()
        self._dlq.clear()
        self._subscribers.clear()


event_bus = EventBus()


async def emit_agent_started(agent_name: str, user_id: str, run_id: str) -> None:
    await event_bus.publish(Event(
        EventType.AGENT_STARTED, {"agent": agent_name, "run_id": run_id},
        source=agent_name, user_id=user_id,
    ))


async def emit_agent_completed(agent_name: str, user_id: str, run_id: str,
                                result: dict) -> None:
    await event_bus.publish(Event(
        EventType.AGENT_COMPLETED, {"agent": agent_name, "run_id": run_id,
                                     "result": result}, source=agent_name, user_id=user_id,
    ))


async def emit_agent_failed(agent_name: str, user_id: str, run_id: str,
                              error: str, retryable: bool) -> None:
    await event_bus.publish(Event(
        EventType.AGENT_FAILED, {"agent": agent_name, "run_id": run_id,
                                  "error": error, "retryable": retryable},
        source=agent_name, user_id=user_id,
    ))


async def emit_workflow_started(workflow_id: str, user_id: str, version: str) -> None:
    await event_bus.publish(Event(
        EventType.WORKFLOW_STARTED, {"workflow_id": workflow_id, "version": version},
        source="orchestrator", user_id=user_id,
    ))


async def emit_workflow_completed(workflow_id: str, user_id: str) -> None:
    await event_bus.publish(Event(
        EventType.WORKFLOW_COMPLETED, {"workflow_id": workflow_id},
        source="orchestrator", user_id=user_id,
    ))


async def emit_workflow_failed(workflow_id: str, user_id: str, error: str) -> None:
    await event_bus.publish(Event(
        EventType.WORKFLOW_FAILED, {"workflow_id": workflow_id, "error": error},
        source="orchestrator", user_id=user_id,
    ))


async def emit_workflow_rolled_back(workflow_id: str, user_id: str,
                                     compensations: list[str]) -> None:
    await event_bus.publish(Event(
        EventType.WORKFLOW_ROLLED_BACK,
        {"workflow_id": workflow_id, "compensations": compensations},
        source="saga", user_id=user_id,
    ))


async def emit_policy_denied(agent_name: str, user_id: str, rule: str) -> None:
    await event_bus.publish(Event(
        EventType.POLICY_DENIED, {"agent": agent_name, "rule": rule},
        source="policy", user_id=user_id,
    ))

# --- Factory ---
def build_event_bus(history_limit: int = 1000, store=None):
    """Construit un EventBus avec son store selon la config.

    `store` peut etre passe explicitement (utile pour les tests et l injection
    depuis main.py). Si None, on lit `settings.event_store_backend` pour choisir
    entre in-memory et sqlite.
    """
    from omniagent.core.config import settings
    dedupe = settings.event_dedupe_window
    if store is not None:
        return EventBus(history_limit=history_limit, store=store, dedupe_window=dedupe)
    backend = (settings.event_store_backend or "memory").lower()
    if backend == "sqlite":
        from omniagent.core.events.store import SqliteEventStore
        return EventBus(
            history_limit=history_limit,
            store=SqliteEventStore(settings.event_store_path),
            dedupe_window=dedupe,
        )
    # defaut : in-memory (zero impact, comportement actuel)
    from omniagent.core.events.store import InMemoryEventStore
    return EventBus(
        history_limit=history_limit,
        store=InMemoryEventStore(history_limit=history_limit),
        dedupe_window=dedupe,
    )
