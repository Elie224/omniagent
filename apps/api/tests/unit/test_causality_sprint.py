"""Tests du Causality Sprint (CausalGraph + migration_policy)."""
from datetime import datetime, timezone

import pytest

from omniagent.core.events.bus import Event, EventBus, EventType
from omniagent.core.events.migration_policy import (
    MigrationDecision, apply_migration_policy, apply_migration_policy_to_stored,
)
from omniagent.core.events.schema import (
    CURRENT_SCHEMA_VERSION, MIGRATIONS, register_migration,
)
from omniagent.core.events.store import InMemoryEventStore, SqliteEventStore
from omniagent.core.observability.causal import (
    CausalGraph, CausalNode, CausalRunTrace, trace_to_tree_dict,
)


# ---------- Migration policy : migration on read ----------

def test_policy_fast_path_when_already_current():
    """Un event deja en version courante : restitue tel quel (fast path)."""
    ev = Event(
        type=EventType.AGENT_STARTED,
        payload={"agent": "x", "run_id": "r1"},
        source="t", schema_version=1,
    )
    out, dec = apply_migration_policy(ev)
    assert out is ev
    assert dec.from_version == 1
    assert dec.to_version == 1
    assert dec.full is True


def test_policy_migrates_payload_to_current_version():
    """Un event v0 -> on migre vers current via le registry."""
    CURRENT_SCHEMA_VERSION["agent.started"] = 2

    def v1_to_v2(p):
        return {**p, "tenant_id": "default"}

    register_migration("agent.started", 1, v1_to_v2)
    try:
        ev = Event(
            type=EventType.AGENT_STARTED,
            payload={"agent": "x", "run_id": "r1"},
            source="t", schema_version=1,
        )
        out, dec = apply_migration_policy(ev)
        # schema_version doit etre updated a 2 (current)
        assert out.schema_version == 2
        assert out.payload.get("tenant_id") == "default"
        assert dec.full is True
    finally:
        del MIGRATIONS["agent.started"]
        CURRENT_SCHEMA_VERSION["agent.started"] = 1


def test_policy_reports_skipped_steps_when_migration_missing():
    """Si une etape manque, on s arrete et on liste les versions skipped."""
    CURRENT_SCHEMA_VERSION["agent.completed"] = 3
    register_migration("agent.completed", 1, lambda p: {**p, "v2_field": True})
    # Pas de v2 -> v3
    try:
        ev = Event(
            type=EventType.AGENT_COMPLETED,
            payload={"agent": "x", "run_id": "r1"},
            source="t", schema_version=1,
        )
        out, dec = apply_migration_policy(ev)
        # On a pu migrer 1->2 mais pas 2->3
        assert dec.full is False
        assert dec.from_version == 1
        assert dec.to_version == 2
        assert 3 in dec.skipped_steps
    finally:
        del MIGRATIONS["agent.completed"]
        CURRENT_SCHEMA_VERSION["agent.completed"] = 1


def test_policy_stored_variant():
    """Variante pour stored events (replay sans reconstruire l Event)."""
    out_payload, version, full = apply_migration_policy_to_stored(
        stored_payload={"agent": "x", "run_id": "r1"},
        stored_type="agent.started",
        stored_version=1,
    )
    # agent.started est en current=1, donc fast path
    assert full is True
    assert version == 1
    assert out_payload == {"agent": "x", "run_id": "r1"}


# ---------- CausalGraph : trace d un run ----------

@pytest.mark.asyncio
async def test_causal_graph_traces_workflow_chain(tmp_path):
    """Un workflow WORKFLOW_STARTED -> AGENT_STARTED -> AGENT_COMPLETED forme un chainage."""
    store = SqliteEventStore(str(tmp_path / "causal.db"))
    bus = EventBus(history_limit=100, store=store)
    corr = "run-causal-1"
    await bus.publish(Event(
        type=EventType.WORKFLOW_STARTED,
        payload={"workflow_id": "w1", "version": "1"},
        source="orchestrator", correlation_id=corr,
    ))
    await bus.publish(Event(
        type=EventType.AGENT_STARTED,
        payload={"agent": "a1", "run_id": "r1"},
        source="a1", correlation_id=corr, causation_id=None,
    ))
    await bus.publish(Event(
        type=EventType.AGENT_COMPLETED,
        payload={"agent": "a1", "run_id": "r1"},
        source="a1", correlation_id=corr, causation_id=None,
    ))

    graph = CausalGraph(bus=bus)
    trace = await graph.trace_run(corr)
    assert trace.total_events == 3
    assert trace.run_id == corr
    # Sans causation_id explicite, on a 3 roots
    assert len(trace.root_ids) >= 1
    # Le noeud WORKFLOW_STARTED existe
    assert any(n.event_type == "workflow.started" for n in trace.nodes.values())


@pytest.mark.asyncio
async def test_causal_graph_infers_parent_via_causation_id(tmp_path):
    """Avec causation_id, le graph relie parent -> enfant."""
    store = SqliteEventStore(str(tmp_path / "causal2.db"))
    bus = EventBus(history_limit=100, store=store)
    corr = "run-causal-2"
    e1 = Event(
        type=EventType.WORKFLOW_STARTED,
        payload={"workflow_id": "w1"},
        source="o", correlation_id=corr,
    )
    await bus.publish(e1)
    e2 = Event(
        type=EventType.AGENT_STARTED,
        payload={"agent": "a1", "run_id": "r1"},
        source="a1", correlation_id=corr, causation_id=e1.event_id,
    )
    await bus.publish(e2)
    e3 = Event(
        type=EventType.AGENT_COMPLETED,
        payload={"agent": "a1", "run_id": "r1"},
        source="a1", correlation_id=corr, causation_id=e2.event_id,
    )
    await bus.publish(e3)

    graph = CausalGraph(bus=bus)
    trace = await graph.trace_run(corr)
    # 1 seul root (e1)
    assert len(trace.root_ids) == 1
    assert trace.root_ids[0] == e1.event_id
    # e2 a e1 comme parent
    node2 = trace.nodes[e2.event_id]
    assert node2.parent_id == e1.event_id
    # e1 a e2 dans children
    node1 = trace.nodes[e1.event_id]
    assert e2.event_id in node1.children_ids
    # e3 a e2 comme parent
    assert trace.nodes[e3.event_id].parent_id == e2.event_id


@pytest.mark.asyncio
async def test_causal_graph_counts_llm_and_connector_calls(tmp_path):
    store = SqliteEventStore(str(tmp_path / "causal3.db"))
    bus = EventBus(history_limit=100, store=store)
    corr = "run-causal-3"
    await bus.publish(Event(
        type=EventType.AGENT_STARTED,
        payload={"agent": "a1", "run_id": "r1", "llm": True, "prompt": "hello"},
        source="a1", correlation_id=corr,
    ))
    await bus.publish(Event(
        type=EventType.CONNECTOR_CALLED,
        payload={"connector": "linkedin", "source": "connector.search"},
        source="connector", correlation_id=corr,
    ))
    await bus.publish(Event(
        type=EventType.AGENT_COMPLETED,
        payload={"agent": "a1", "run_id": "r1"},
        source="a1", correlation_id=corr,
    ))
    graph = CausalGraph(bus=bus)
    trace = await graph.trace_run(corr)
    assert trace.llm_calls == 1
    assert trace.connector_calls == 1


@pytest.mark.asyncio
async def test_causal_graph_computes_duration(tmp_path):
    store = SqliteEventStore(str(tmp_path / "causal4.db"))
    bus = EventBus(history_limit=100, store=store)
    corr = "run-causal-4"
    await bus.publish(Event(
        type=EventType.WORKFLOW_STARTED,
        payload={"workflow_id": "w1"},
        source="o", correlation_id=corr,
    ))
    import asyncio
    await asyncio.sleep(0.05)
    await bus.publish(Event(
        type=EventType.WORKFLOW_COMPLETED,
        payload={"workflow_id": "w1"},
        source="o", correlation_id=corr,
    ))
    graph = CausalGraph(bus=bus)
    trace = await graph.trace_run(corr)
    # Au moins 50ms de duree
    assert trace.duration_ms >= 50.0


@pytest.mark.asyncio
async def test_causal_graph_trace_recent_runs(tmp_path):
    store = SqliteEventStore(str(tmp_path / "causal5.db"))
    bus = EventBus(history_limit=100, store=store)
    # 3 runs distincts, 1 event chacun
    for i in range(3):
        await bus.publish(Event(
            type=EventType.WORKFLOW_STARTED,
            payload={"workflow_id": f"w{i}"},
            source="o", correlation_id=f"recent-{i}",
        ))
    graph = CausalGraph(bus=bus)
    traces = await graph.trace_recent_runs(limit=2)
    assert len(traces) == 2
    run_ids = {t.run_id for t in traces}
    # Les 2 plus recents (recent-1 et recent-2 ou recent-0 selon timestamp)
    assert run_ids.issubset({"recent-0", "recent-1", "recent-2"})


@pytest.mark.asyncio
async def test_causal_graph_empty_run():
    bus = EventBus(history_limit=10, store=InMemoryEventStore())
    graph = CausalGraph(bus=bus)
    trace = await graph.trace_run("nonexistent-run")
    assert trace.total_events == 0
    assert trace.root_ids == []
    assert trace.llm_calls == 0
    assert trace.connector_calls == 0


def test_trace_to_tree_dict_serialization():
    """Le tree dict est serialisable JSON-friendly pour affichage UI."""
    trace = CausalRunTrace(run_id="r1")
    n1 = CausalNode(node_id="n1", node_type="event",
                    event_type="workflow.started", timestamp="t1")
    n2 = CausalNode(node_id="n2", node_type="event",
                    event_type="agent.started", timestamp="t2",
                    parent_id="n1")
    n1.children_ids.append("n2")
    trace.nodes = {"n1": n1, "n2": n2}
    trace.root_ids = ["n1"]
    tree = trace_to_tree_dict(trace)
    assert "roots" in tree or "children" in tree
    # Single root : renvoie directement l arbre
    single = trace_to_tree_dict(trace, "n1")
    assert single["id"] == "n1"
    assert single["type"] == "workflow.started"
    assert len(single["children"]) == 1
    assert single["children"][0]["id"] == "n2"