"""Causal Graph : relations causales entre runs, events, et side effects.

But : repondre a des questions de debug du type :
- "Quels events ont conduit a ce run ?"
- "Quel event a declenche cet appel LLM ?"
- "Quels connecteurs ont ete touches par ce run ?"
- "Quelle est la chaine causale complete de ce workflow ?"

Modele de donnees :

  run_id (workflow / orchestrateur run)
    |
    +-- events (WORKFLOW_*, AGENT_*) filtres par correlation_id
    |
    +-- child calls (LLM calls, connector calls) infers via metadata

Construction :
- On scanne l EventStore, on groupe par correlation_id
- Pour chaque correlation_id, on trie par timestamp
- On en deduit un arbre : WORKFLOW_STARTED -> AGENT_STARTED -> TOOL_EXECUTED

Note : MVP. Le graphe est recalcule a la demande (pas de projection
persistee). Pour des volumes plus gros on ajoutera une table dediee.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from omniagent.core.events.bus import EventBus


@dataclass
class CausalNode:
    """Un noeud du graphe : un event ou un child call."""
    node_id: str
    node_type: str          # "event" | "llm_call" | "connector_call"
    event_type: str         # type d event ou nom du call
    timestamp: str
    payload: dict = field(default_factory=dict)
    parent_id: str | None = None
    children_ids: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class CausalRunTrace:
    """Trace causale complete d un run."""
    run_id: str                          # correlation_id du run
    nodes: dict[str, CausalNode] = field(default_factory=dict)
    root_ids: list[str] = field(default_factory=list)
    total_events: int = 0
    llm_calls: int = 0
    connector_calls: int = 0
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "total_events": self.total_events,
            "llm_calls": self.llm_calls,
            "connector_calls": self.connector_calls,
            "duration_ms": self.duration_ms,
            "roots": self.root_ids,
            "nodes": {nid: {
                "node_type": n.node_type,
                "event_type": n.event_type,
                "timestamp": n.timestamp,
                "parent_id": n.parent_id,
                "children_ids": n.children_ids,
                "payload": n.payload,
            } for nid, n in self.nodes.items()},
        }


def _is_llm_call_payload(payload: dict) -> bool:
    """Heuristique : reconnait un payload d appel LLM."""
    return ("llm" in str(payload).lower() and
            ("prompt" in payload or "model" in payload or "tokens_in" in payload))


def _is_connector_call_payload(payload: dict) -> bool:
    """Heuristique : reconnait un payload d appel connecteur."""
    return ("connector" in payload or
            "call_name" in payload or
            ("source" in payload and payload.get("source", "").startswith("connector")))


class CausalGraph:
    """Reconstruit le graphe causal d un run depuis les events du store."""

    def __init__(self, bus: "EventBus | None" = None):
        self._bus = bus

    def _get_bus(self) -> "EventBus":
        if self._bus is not None:
            return self._bus
        from omniagent.core.events import get_event_bus
        return get_event_bus()

    async def trace_run(self, run_id: str, since: datetime | None = None) -> CausalRunTrace:
        """Retourne la trace causale complete pour un correlation_id.

        Algorithme :
        1. Query le store pour tous les events lies a `run_id` (correlation_id)
        2. Trier par timestamp
        3. Construire les noeuds, inferer les parents via causation_id
        4. Identifier les roots (events WORKFLOW_STARTED ou AGENT_STARTED
           sans parent)
        """
        bus = self._get_bus()
        store = bus.get_store() if hasattr(bus, "get_store") else None
        if store is None:
            return CausalRunTrace(run_id=run_id)

        events = await store.query(
            correlation_id=run_id,
            since=since,
            limit=10_000,
        )
        events_sorted = sorted(events, key=lambda e: e.timestamp)

        nodes: dict[str, CausalNode] = {}
        parent_of: dict[str, str] = {}  # child_event_id -> parent_event_id
        ts_min: datetime | None = None
        ts_max: datetime | None = None
        llm_calls = 0
        connector_calls = 0

        # 1ere passe : creer les noeuds et detecter les relations de causalite
        for stored in events_sorted:
            node = CausalNode(
                node_id=stored.event_id,
                node_type="event",
                event_type=stored.type,
                timestamp=stored.timestamp,
                payload=stored.payload,
                metadata={
                    "source": stored.source,
                    "user_id": stored.user_id,
                    "causation_id": stored.causation_id,
                },
            )
            nodes[stored.event_id] = node
            if stored.causation_id and stored.causation_id in nodes:
                parent_of[stored.event_id] = stored.causation_id
                node.parent_id = stored.causation_id
            # Heuristique secondaire : si pas de causation_id, on regarde si
            # le payload pointe vers un autre event (event_id dans le payload)
            elif "parent_event_id" in stored.payload:
                pid = stored.payload["parent_event_id"]
                if pid in nodes:
                    parent_of[stored.event_id] = pid
                    node.parent_id = pid

            # Compteurs et ranges
            try:
                ts = datetime.fromisoformat(stored.timestamp)
                if ts_min is None or ts < ts_min:
                    ts_min = ts
                if ts_max is None or ts > ts_max:
                    ts_max = ts
            except (TypeError, ValueError):
                pass

            if _is_llm_call_payload(stored.payload):
                llm_calls += 1
            if _is_connector_call_payload(stored.payload):
                connector_calls += 1

        # 2eme passe : remplir les children de chaque parent
        for child_id, parent_id in parent_of.items():
            p = nodes.get(parent_id)
            if p is not None and child_id not in p.children_ids:
                p.children_ids.append(child_id)

        # Identifier les roots
        children_set = set(parent_of.keys())
        roots = [nid for nid in nodes.keys() if nid not in children_set]

        # Duree
        duration_ms = 0.0
        if ts_min is not None and ts_max is not None:
            duration_ms = (ts_max - ts_min).total_seconds() * 1000.0

        return CausalRunTrace(
            run_id=run_id,
            nodes=nodes,
            root_ids=roots,
            total_events=len(events_sorted),
            llm_calls=llm_calls,
            connector_calls=connector_calls,
            duration_ms=duration_ms,
        )

    async def trace_recent_runs(self, limit: int = 20) -> list[CausalRunTrace]:
        """Retourne les traces des N derniers runs (par correlation_id distinct).

        Strategie : on query les events, on regroupe par correlation_id, on
        garde les N plus recents et on retourne leurs traces.
        """
        bus = self._get_bus()
        store = bus.get_store() if hasattr(bus, "get_store") else None
        if store is None:
            return []

        # Query large puis regroupement
        all_events = await store.query(limit=50_000)
        by_corr: dict[str, list] = defaultdict(list)
        for ev in all_events:
            if ev.correlation_id:
                by_corr[ev.correlation_id].append(ev)

        # Prendre les `limit` plus recents
        sorted_corr = sorted(
            by_corr.keys(),
            key=lambda cid: max(e.timestamp for e in by_corr[cid]),
            reverse=True,
        )[:limit]

        traces = []
        for cid in sorted_corr:
            t = await self.trace_run(cid)
            traces.append(t)
        return traces


def trace_to_tree_dict(trace: CausalRunTrace, node_id: str | None = None) -> dict:
    """Serialise un sous-arbre du trace en dict pour affichage."""
    if node_id is None:
        if not trace.root_ids:
            return {}
        # Si plusieurs roots, on les liste
        if len(trace.root_ids) == 1:
            return trace_to_tree_dict(trace, trace.root_ids[0])
        return {
            "run_id": trace.run_id,
            "roots": [trace_to_tree_dict(trace, rid) for rid in trace.root_ids],
        }
    node = trace.nodes.get(node_id)
    if node is None:
        return {}
    return {
        "id": node.node_id,
        "type": node.event_type,
        "timestamp": node.timestamp,
        "children": [trace_to_tree_dict(trace, cid) for cid in node.children_ids],
    }