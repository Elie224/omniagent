"""Bus evenementiel asynchrone interne (in-process).

NOTE ARCHITECTURALE (unification Sprint 3) :
Ce module est un shim de retrocompatibilite. Toute la logique (EventType, Event,
EventBus, event_bus module-level) est definie dans `omniagent.core.events.bus`.

On garde ici UNIQUEMENT les re-exports et la resolution du bus actif (DI via
app.state.event_bus si FastAPI est monte, sinon le singleton module-level pour
les tests unitaires et le mode hors-app).

But : eliminer la double source de verite. Apres cette migration, il n y a plus
qu UN SEUL EventBus, et tous les `emit_*` passent par lui.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from omniagent.core.events.bus import (
    Event,
    EventBus,
    EventType,
    SubscriberCallback,
    build_event_bus,
    emit_agent_completed,
    emit_agent_failed,
    emit_agent_started,
    emit_policy_denied,
    emit_workflow_completed,
    emit_workflow_failed,
    emit_workflow_rolled_back,
    emit_workflow_started,
    event_bus,
)


def get_event_bus() -> EventBus:
    """Retourne le bus actif.

    Resolution par ordre :
    1. `app.state.event_bus` (celui du lifespan, avec le store selectionne)
    2. Le singleton module-level `event_bus` (fallback pour tests / hors-app)

    C est cette fonction que les helpers `emit_*` appellent en interne, ce qui
    garantit qu un event emis depuis un agent/connecteur transite par le MEME
    bus que celui expose par /api/v1/shared/events/query.
    """
    try:
        from omniagent.main import app  # import local pour eviter cycle
        state_bus = getattr(app.state, "event_bus", None)
        if state_bus is not None:
            return state_bus
    except Exception:
        # Pas de FastAPI monte (test unitaire, script) -> fallback module-level
        pass
    return event_bus


# Wrappers : on bind le bus au moment de l appel, pas a l import, pour beneficier
# automatiquement de la resolution ci-dessus.
async def _publish_via_active_bus(event: Event) -> int:
    return await get_event_bus().publish(event)


# Helpers exposes via le module `omniagent.core.events` (et pas `bus`) pour
# ne pas casser les imports existants du genre
#   from omniagent.core.events import emit_agent_started
# Tout en faisant transiter les events par le bus actif.

# Note : les `emit_*` de `bus.py` utilisent le module-level `event_bus` capture
# a l import. Pour la migration, on les redefinit ici en passant par
# get_event_bus(). On garde les memes signatures pour eviter tout changement
# d appelant.

async def emit_agent_started(agent_name: str, user_id: str, run_id: str) -> int:
    return await _publish_via_active_bus(Event(
        EventType.AGENT_STARTED, {"agent": agent_name, "run_id": run_id},
        source=agent_name, user_id=user_id,
    ))


async def emit_agent_completed(agent_name: str, user_id: str, run_id: str,
                                result: dict) -> int:
    return await _publish_via_active_bus(Event(
        EventType.AGENT_COMPLETED, {"agent": agent_name, "run_id": run_id,
                                     "result": result}, source=agent_name, user_id=user_id,
    ))


async def emit_agent_failed(agent_name: str, user_id: str, run_id: str,
                              error: str, retryable: bool) -> int:
    return await _publish_via_active_bus(Event(
        EventType.AGENT_FAILED, {"agent": agent_name, "run_id": run_id,
                                  "error": error, "retryable": retryable},
        source=agent_name, user_id=user_id,
    ))


async def emit_workflow_started(workflow_id: str, user_id: str, version: str) -> int:
    return await _publish_via_active_bus(Event(
        EventType.WORKFLOW_STARTED, {"workflow_id": workflow_id, "version": version},
        source="orchestrator", user_id=user_id,
    ))


async def emit_workflow_completed(workflow_id: str, user_id: str) -> int:
    return await _publish_via_active_bus(Event(
        EventType.WORKFLOW_COMPLETED, {"workflow_id": workflow_id},
        source="orchestrator", user_id=user_id,
    ))


async def emit_workflow_failed(workflow_id: str, user_id: str, error: str) -> int:
    return await _publish_via_active_bus(Event(
        EventType.WORKFLOW_FAILED, {"workflow_id": workflow_id, "error": error},
        source="orchestrator", user_id=user_id,
    ))


async def emit_workflow_rolled_back(workflow_id: str, user_id: str,
                                     compensations: list[str]) -> int:
    return await _publish_via_active_bus(Event(
        EventType.WORKFLOW_ROLLED_BACK,
        {"workflow_id": workflow_id, "compensations": compensations},
        source="saga", user_id=user_id,
    ))


async def emit_policy_denied(agent_name: str, user_id: str, rule: str) -> int:
    return await _publish_via_active_bus(Event(
        EventType.POLICY_DENIED, {"agent": agent_name, "rule": rule},
        source="policy", user_id=user_id,
    ))


__all__ = [
    "Event", "EventBus", "EventType", "SubscriberCallback",
    "build_event_bus", "event_bus", "get_event_bus",
    "emit_agent_started", "emit_agent_completed", "emit_agent_failed",
    "emit_workflow_started", "emit_workflow_completed",
    "emit_workflow_failed", "emit_workflow_rolled_back",
    "emit_policy_denied",
]


if TYPE_CHECKING:
    # Evite les cycles d import a l analyse statique
    pass