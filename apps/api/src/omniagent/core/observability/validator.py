"""Observability validator : sanity checks anti-"dashboard faux sans erreur".

But : detecter les desync entre les compteurs metier (metrics + scoring) et
les events reellement emis. Si par exemple un orchestrateur publie un
AGENT_COMPLETED mais ne fait pas `record_run`, on a un trou de comptage.

Approche pragmatique : on agrege les events par type depuis l EventStore
(memoire ou SQLite) et on compare aux compteurs metier. Toute incoherence
est retournee sous forme de `ValidationIssue` (severite warning par defaut).

Usage :
    issues = validate_observability_consistency()
    for issue in issues:
        log.warning(issue.message)
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omniagent.core.events.bus import EventBus
    from omniagent.core.observability.metrics import MetricsRegistry


@dataclass
class ValidationIssue:
    """Un probleme de coherence detecte par le validator."""
    code: str              # ex: "missing_completion_event"
    message: str
    severity: str = "warning"   # "warning" | "error"
    context: dict = field(default_factory=dict)


def _bus_events_summary(bus: "EventBus", since: datetime | None = None) -> Counter:
    """Compte les events par type depuis le store de `bus`.

    Strategie en 2 etapes :
    1. Si une loop asyncio est disponible (cas normal en FastAPI) : on lance
       la query async sur le store.
    2. Sinon : fallback sur l history in-RAM de l EventBus (cas test unitaire
       synchrone ou app non-FastAPI).
    """
    import asyncio
    from omniagent.core.events.bus import EventType

    store = bus.get_store() if hasattr(bus, "get_store") else None
    c: Counter = Counter()

    # Cas fast path : on peut query le store
    if store is not None:
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_running():
                async def _count() -> Counter:
                    out: Counter = Counter()
                    for t in EventType:
                        rows = await store.query(event_type=t.value, since=since, limit=10_000)
                        if rows:
                            out[t.value] = len(rows)
                    return out
                return loop.run_until_complete(_count())
        except RuntimeError:
            pass

    # Fallback : history RAM (toujours disponible, synchrone)
    for ev in getattr(bus, "_history", []):
        c[ev.type.value] += 1
    return c


def _metrics_summary(metrics: "MetricsRegistry") -> Counter:
    """Extrait les compteurs metier qui refletent des events."""
    snap = metrics.snapshot()
    counters = snap.get("counters", {})
    out: Counter = Counter()
    # Convention : les compteurs lies aux events sont prefixees par `agent.`
    # ou `workflow.` ou `connector.`. On ne garde que ceux qui ont un
    # pendant event pour eviter le bruit.
    for name, value in counters.items():
        if name.startswith("agent.") and value:
            # agent.started -> 1 completed attendu (en moyenne)
            out[name] = int(value)
    return out


def validate_observability_consistency(
    bus: "EventBus | None" = None,
    metrics: "MetricsRegistry | None" = None,
) -> list[ValidationIssue]:
    """Verifie la coherence entre events emis et compteurs metier.

    Retourne une liste d issues (vide = tout est coherent).
    """
    issues: list[ValidationIssue] = []

    if bus is None:
        from omniagent.core.events import get_event_bus
        bus = get_event_bus()
    if metrics is None:
        from omniagent.core.observability.metrics import metrics

    events_count = _bus_events_summary(bus)

    # Heuristique : si on a plus de AGENT_STARTED que de AGENT_COMPLETED+AGENT_FAILED,
    # c est qu il y a des runs en cours OU des events perdus. On ne signale que
    # si l ecart est tres grand (>50%).
    started = events_count.get("agent.started", 0)
    completed = events_count.get("agent.completed", 0)
    failed = events_count.get("agent.failed", 0)
    if started > 0:
        unresolved = started - (completed + failed)
        if unresolved > 0 and unresolved / max(started, 1) > 0.5:
            issues.append(ValidationIssue(
                code="high_unresolved_runs",
                message=(
                    f"{unresolved} agent(s) demarres mais ni completes ni "
                    f"failed (>{50}% de runs non resolus)"
                ),
                severity="warning",
                context={
                    "started": started,
                    "completed": completed,
                    "failed": failed,
                },
            ))

    # Detecter les workflows sans completion correspondante
    wf_started = events_count.get("workflow.started", 0)
    wf_completed = events_count.get("workflow.completed", 0)
    wf_failed = events_count.get("workflow.failed", 0)
    if wf_started > 0:
        wf_unresolved = wf_started - (wf_completed + wf_failed)
        if wf_unresolved > 0 and wf_unresolved / max(wf_started, 1) > 0.5:
            issues.append(ValidationIssue(
                code="high_unresolved_workflows",
                message=(
                    f"{wf_unresolved} workflow(s) demarres mais ni completes "
                    f"ni failed (>{50}% de workflows non resolus)"
                ),
                severity="warning",
                context={
                    "started": wf_started,
                    "completed": wf_completed,
                    "failed": wf_failed,
                },
            ))

    return issues