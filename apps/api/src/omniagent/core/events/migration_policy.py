"""Migration ownership policy : regle unique d autorite sur les versions d events.

PROBLEME : un event dans le store peut etre en schema_version=N, le consumer
peut etre en version M>=N, et le replay peut mixer. Sans regle unique, on a
des divergences silencieuses (un event N lu comme M sans migration, ou
un event N re-migre plusieurs fois).

DECISION ARCHITECTURALE (Sprint 3+) : MIGRATION ON READ.

Pourquoi "on read" plutot que "on write" :
- Le store reste raw/immutable : on ne mute jamais un event stocke.
- La projection (replay, dashboard, query) applique la migration au moment
  de la lecture, de maniere transparente et idempotente.
- Permet de rollback une migration sans toucher au store.
- Permet a plusieurs consumers de tourner sur des versions differentes.

Tradeoffs :
- Cout CPU au read (migration a chaque query) -> acceptable car on a un
  registry de migrations in-memory.
- Pas de migration eager (rejouer un event N fois = N migrations) ->
  acceptable car idempotent.

Regles concretes :
- A l ecriture : l event est stocke avec son schema_version natif.
- A la lecture (replay, query, dashboard) : on appelle
  `apply_migration_policy(event) -> Event` qui migre vers CURRENT_SCHEMA_VERSION
  avant de delivrer au consumer.
- Un event deja en version courante est restitue tel quel (fast path).
- Si une migration est manquante pour aller jusqu a current, on log un
  warning et on restitue la derniere version atteinte (anti-break).
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING

from omniagent.core.events.bus import Event
from omniagent.core.events.schema import (
    CURRENT_SCHEMA_VERSION, migrate_payload,
)

if TYPE_CHECKING:
    pass


@dataclass
class MigrationDecision:
    """Diagnostic d une decision de migration."""
    event_id: str
    event_type: str
    from_version: int
    to_version: int
    full: bool  # True si on a atteint CURRENT_SCHEMA_VERSION
    skipped_steps: list[int]  # versions pour lesquelles la migration manque


def apply_migration_policy(event: Event) -> tuple[Event, MigrationDecision]:
    """Applique la policy de migration a un event avant livraison.

    Retourne (event_migre, decision). Si l event est deja en version courante,
    on restitue tel quel (fast path). Sinon on migre via le registry.

    Le consumer recoit un Event en version courante (ou la derniere atteinte
    si une migration manque). Les donnees payload sont migrees, le reste
    des champs est preserve.
    """
    target_version = CURRENT_SCHEMA_VERSION.get(event.type.value, 1)
    if event.schema_version >= target_version:
        # Fast path : rien a faire
        return event, MigrationDecision(
            event_id=event.event_id,
            event_type=event.type.value,
            from_version=event.schema_version,
            to_version=event.schema_version,
            full=True,
            skipped_steps=[],
        )

    # On migre
    from_version = event.schema_version
    new_payload, reached = migrate_payload(event.type.value, event.payload, from_version)
    full = reached >= target_version
    skipped = list(range(reached + 1, target_version + 1)) if not full else []

    migrated = Event(
        type=event.type,
        payload=new_payload,
        source=event.source,
        timestamp=event.timestamp,
        event_id=event.event_id,
        correlation_id=event.correlation_id,
        causation_id=event.causation_id,
        user_id=event.user_id,
        schema_version=reached,
    )
    return migrated, MigrationDecision(
        event_id=event.event_id,
        event_type=event.type.value,
        from_version=from_version,
        to_version=reached,
        full=full,
        skipped_steps=skipped,
    )


def apply_migration_policy_to_stored(
    stored_payload: dict,
    stored_type: str,
    stored_version: int,
) -> tuple[dict, int, bool]:
    """Variante pour les donnees du store (avant reconstruction d un Event).

    Utile pour les projections (replay, dashboard) qui veulent le payload
    migre sans reconstruire l Event complet.

    Retourne (payload_migre, version_atteinte, full).
    """
    target = CURRENT_SCHEMA_VERSION.get(stored_type, 1)
    if stored_version >= target:
        return stored_payload, stored_version, True
    new_payload, reached = migrate_payload(stored_type, stored_payload, stored_version)
    return new_payload, reached, reached >= target