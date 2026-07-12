"""Event Replay Engine : rejoue des events depuis le store vers un consumer.

Use cases :
- Debug production : on recupere tous les events lies a un correlation_id et
  on les rejoue dans un consumer de test pour reproduire un bug.
- A/B test agents : on prend un historique reel et on le re-publie dans un
  orchestrateur modifie pour comparer les outcomes.
- Dry-run : on rejoue sans declencher les side effects reels (le consumer
  decide quoi faire, ex: logger au lieu d envoyer un email).

API :
    bus.replay(correlation_id=..., since=..., into=callback, dry_run=True)

Retourne le nombre d events rejoues.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable

from .bus import Event, EventBus, EventType
from .store import StoredEvent


ReplayCallback = Callable[[Event], Awaitable[None]]


@dataclass
class ReplayResult:
    """Resultat d un replay, avec diagnostics."""
    events_scanned: int
    events_replayed: int
    events_skipped: int
    errors: list[str]
    dry_run: bool
    correlation_id: str | None = None


def _stored_to_event(stored: StoredEvent) -> Event:
    """Reconstruit un Event a partir d un StoredEvent (lecture du store)."""
    return Event(
        type=EventType(stored.type),
        payload=stored.payload,
        source=stored.source,
        timestamp=datetime.fromisoformat(stored.timestamp),
        event_id=stored.event_id,
        correlation_id=stored.correlation_id,
        causation_id=stored.causation_id,
        user_id=stored.user_id,
    )


async def replay(
    bus: EventBus,
    *,
    correlation_id: str | None = None,
    since: datetime | None = None,
    event_type: EventType | None = None,
    into: ReplayCallback,
    dry_run: bool = True,
) -> ReplayResult:
    """Rejoue des events depuis le store de `bus` vers `into`.

    Parametres :
    - correlation_id : filtre par correlation_id (workflow, run_id, etc.)
    - since : filtre temporel (events plus recents que `since`)
    - event_type : filtre par type d event
    - into : coroutine appelee pour chaque event rejoue
    - dry_run : si True, on logge sans modifier l etat (le store n est pas
      re-mis a jour, les subscribers ne sont pas notifies)

    Retours :
    - ReplayResult avec compteurs et erreurs
    """
    store = bus.get_store() if hasattr(bus, "get_store") else None
    if store is None:
        return ReplayResult(
            events_scanned=0, events_replayed=0, events_skipped=0,
            errors=["event store non initialise"],
            dry_run=dry_run, correlation_id=correlation_id,
        )

    events = await store.query(
        event_type=event_type.value if event_type else None,
        correlation_id=correlation_id,
        since=since,
        limit=10_000,  # borne haute de securite pour un replay
    )

    replayed = 0
    skipped = 0
    errors: list[str] = []
    for stored in events:
        ev = _stored_to_event(stored)
        try:
            if dry_run:
                # En dry-run on n appelle PAS into (ou on appelle un no-op
                # pour valider le contrat). Le consumer doit etre explicite.
                replayed += 1
            else:
                await into(ev)
                replayed += 1
        except Exception as e:
            errors.append(f"{stored.event_id}: {type(e).__name__}: {e}")
            skipped += 1

    return ReplayResult(
        events_scanned=len(events),
        events_replayed=replayed,
        events_skipped=skipped,
        errors=errors,
        dry_run=dry_run,
        correlation_id=correlation_id,
    )


async def replay_into_bus(
    bus: EventBus,
    *,
    correlation_id: str | None = None,
    since: datetime | None = None,
    event_type: EventType | None = None,
    target_bus: EventBus | None = None,
    dry_run: bool = True,
) -> ReplayResult:
    """Variante de replay qui re-publie dans un autre bus (ou le meme).

    Si `target_bus` est None, on re-publie dans `bus` lui-meme (utile avec
    dedupe active pour ne pas re-notifier les subscribers, ou pour
    reinitialiser un contexte apres crash).

    ATTENTION : si dedupe est active sur le bus cible, les events ayant le
    meme `event_id` seront ignores. C est le comportement desire pour
    eviter le double-traitement, mais ca veut dire qu un replay ne
    re-declenche pas les side effects si les events ont deja ete traites.
    """
    target = target_bus or bus

    async def republish(ev: Event) -> None:
        await target.publish(ev)

    return await replay(
        bus,
        correlation_id=correlation_id,
        since=since,
        event_type=event_type,
        into=republish,
        dry_run=dry_run,
    )