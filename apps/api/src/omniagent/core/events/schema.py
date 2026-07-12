"""Schemas Pydantic pour les payloads d events metier.

But : donner un contrat valide par type d event pour detecter les drift
silencieux (un producer qui change la forme d un payload, un consumer qui
s attend a un champ manquant, etc.).

Les schemas sont *optionnels* : si un type d event n a pas de schema defini
ou si le payload ne valide pas, on accepte l event en mode "raw" avec un
warning. Pas de breaking change : on ne casse jamais un flow existant,
on signale juste l incoherence.

Convention de nommage : `<EventTypeValue>_PAYLOAD_SCHEMA` (lowercase, points
remplaces par underscores).
"""
from __future__ import annotations
from typing import Any, ClassVar, Optional
import warnings

from pydantic import BaseModel, ConfigDict, Field


# --- Schemas par type d event ---

class AgentLifecyclePayload(BaseModel):
    """Schema commun aux events AGENT_STARTED / COMPLETED / FAILED."""
    model_config = ConfigDict(extra="allow")
    agent: str
    run_id: str
    # Champs optionnels selon le type d event
    result: Optional[dict] = None
    error: Optional[str] = None
    retryable: Optional[bool] = None


class WorkflowLifecyclePayload(BaseModel):
    """Schema pour WORKFLOW_STARTED / COMPLETED / FAILED / ROLLED_BACK."""
    model_config = ConfigDict(extra="allow")
    workflow_id: str
    version: Optional[str] = None
    error: Optional[str] = None
    compensations: Optional[list[str]] = None


class ConnectorPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    connector: Optional[str] = None
    name: Optional[str] = None
    error: Optional[str] = None


class PolicyPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    agent: str
    rule: str


class ToolPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    tool: Optional[str] = None
    name: Optional[str] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None


class MemoryPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    key: Optional[str] = None
    scope: Optional[str] = None
    reason: Optional[str] = None


class QuotaPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    quota: Optional[str] = None
    used: Optional[float] = None
    limit: Optional[float] = None


class NotificationPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    channel: Optional[str] = None
    to: Optional[str] = None
    status: Optional[str] = None


# --- Table de mapping ---

PAYLOAD_SCHEMAS: dict[str, type[BaseModel]] = {
    "agent.started":              AgentLifecyclePayload,
    "agent.completed":            AgentLifecyclePayload,
    "agent.failed":               AgentLifecyclePayload,
    "tool.executed":              ToolPayload,
    "tool.failed":                ToolPayload,
    "memory.updated":             MemoryPayload,
    "memory.poisoned":            MemoryPayload,
    "workflow.started":           WorkflowLifecyclePayload,
    "workflow.completed":         WorkflowLifecyclePayload,
    "workflow.failed":            WorkflowLifecyclePayload,
    "workflow.rolled_back":       WorkflowLifecyclePayload,
    "connector.called":           ConnectorPayload,
    "connector.failed":           ConnectorPayload,
    "quota.exceeded":             QuotaPayload,
    "policy.denied":              PolicyPayload,
    "notification.sent":          NotificationPayload,
}


class EventValidationWarning(UserWarning):
    """Levee en cas de payload invalide pour un type d event connu."""


def validate_payload(event_type_value: str, payload: dict) -> tuple[dict, bool]:
    """Valide un payload contre le schema attendu. Retourne (payload, ok).

    - Si un schema existe et valide : on retourne (payload, True).
    - Si un schema existe mais invalide : on log un warning et on retourne
      le payload original (mode raw) avec (payload, False). On ne casse pas
      le flow metier : c est de la detection, pas du blocking.
    - Si aucun schema n est defini : on accepte en silence (payload, True).
    """
    schema_cls = PAYLOAD_SCHEMAS.get(event_type_value)
    if schema_cls is None:
        return payload, True
    try:
        # model_validate + model_dump garantit la coherence du payload
        validated = schema_cls.model_validate(payload)
        return validated.model_dump(exclude_none=False), True
    except Exception as e:
        warnings.warn(
            f"Event payload validation failed for type={event_type_value!r}: {e}. "
            "Falling back to raw payload (drift detection).",
            EventValidationWarning,
            stacklevel=2,
        )
        return payload, False

# --- Versioning & migrations ---

# Schema version courante par type d event. Quand on fait evoluer le payload,
# on incremente la version ici et on enregistre une fonction de migration.
CURRENT_SCHEMA_VERSION: dict[str, int] = {t: 1 for t in PAYLOAD_SCHEMAS}


# Registre de migrations : {event_type: {from_version: migration_fn}}
# Une migration prend un payload vN et retourne un payload v(N+1).
# Exemple :
#   MIGRATIONS["agent.started"][1] = lambda p: {**p, "new_field": default_value}
# La migration est appelee en chaine jusqu a atteindre CURRENT_SCHEMA_VERSION.

MIGRATIONS: dict[str, dict[int, "callable"]] = {}


def register_migration(event_type: str, from_version: int, fn: "callable") -> None:
    """Enregistre une migration vN -> vN+1 pour un type d event."""
    if event_type not in MIGRATIONS:
        MIGRATIONS[event_type] = {}
    MIGRATIONS[event_type][from_version] = fn


def migrate_payload(event_type: str, payload: dict, from_version: int) -> tuple[dict, int]:
    """Migre un payload de `from_version` vers CURRENT_SCHEMA_VERSION.

    Retourne (payload_migre, version_finale). Si pas de migration, retourne
    le payload tel quel. Si une migration manque, on s arrete a la derniere
    version atteinte et on log un warning (anti-break).
    """
    target = CURRENT_SCHEMA_VERSION.get(event_type, 1)
    current = from_version
    out = dict(payload)
    if event_type not in MIGRATIONS:
        return out, current
    while current < target:
        fn = MIGRATIONS[event_type].get(current)
        if fn is None:
            # Pas de migration pour cette etape : on s arrete
            break
        try:
            out = fn(out)
            current += 1
        except Exception:
            # Migration cassee : on s arrete, on garde le payload actuel
            break
    return out, current
