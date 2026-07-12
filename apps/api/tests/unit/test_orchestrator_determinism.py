"""Tests du Deterministic Orchestrator Hardening."""
import asyncio
from datetime import datetime, timezone

import pytest

from omniagent.core.orchestrator.determinism import (
    DeterministicPlannerError, ExecutionGraph, ExecutionNode, StepStatus,
    assert_deterministic_plan, assert_step_ids_unique,
    assign_step_ids, derive_step_id,
)
from omniagent.core.orchestrator.planner.base import Plan, PlanStep, TemplatePlanner


# ---------- derive_step_id ----------

def test_derive_step_id_is_deterministic():
    a = derive_step_id("search_job", "1.0", "agent_emploi", 0)
    b = derive_step_id("search_job", "1.0", "agent_emploi", 0)
    assert a == b
    assert "search_job" in a
    assert "agent_emploi" in a
    assert "#0:" in a


def test_derive_step_id_differs_by_index():
    a = derive_step_id("p", "1.0", "x", 0)
    b = derive_step_id("p", "1.0", "x", 1)
    assert a != b


def test_derive_step_id_differs_by_agent():
    a = derive_step_id("p", "1.0", "x", 0)
    b = derive_step_id("p", "1.0", "y", 0)
    assert a != b


# ---------- assign_step_ids ----------

def test_assign_step_ids_returns_unique_ids():
    ids = assign_step_ids("plan1", "1.0", ["a", "b", "c"])
    assert len(ids) == 3
    assert len(set(ids)) == 3  # tous uniques


def test_assign_step_ids_is_deterministic():
    a = assign_step_ids("plan1", "1.0", ["a", "b", "c"])
    b = assign_step_ids("plan1", "1.0", ["a", "b", "c"])
    assert a == b


def test_assert_step_ids_unique_raises_on_dup():
    with pytest.raises(ValueError, match="doublon"):
        assert_step_ids_unique(["a", "b", "a"])


# ---------- ExecutionGraph : live construction ----------

def test_execution_graph_starts_empty():
    g = ExecutionGraph(run_id="r1", plan_name="p", plan_version="1.0")
    assert g.nodes == {}
    assert g.roots == []
    stats = g.stats()
    assert stats["total_steps"] == 0
    assert stats["by_status"] == {}


def test_add_root_creates_node_and_marks_as_root():
    g = ExecutionGraph("r1", "p", "1.0")
    g.add_root("s1", "agent_x")
    assert "s1" in g.roots
    assert g.nodes["s1"].agent_name == "agent_x"
    assert g.nodes["s1"].status == StepStatus.PENDING


def test_add_root_is_idempotent():
    g = ExecutionGraph("r1", "p", "1.0")
    g.add_root("s1", "agent_x")
    g.add_root("s1", "agent_y")  # ne doit pas ecraser ni dupliquer
    assert g.roots == ["s1"]
    assert g.nodes["s1"].agent_name == "agent_x"  # 1er gagne


def test_begin_step_creates_node_with_parent_link():
    g = ExecutionGraph("r1", "p", "1.0")
    g.add_root("s1", "agent_a")
    g.begin_step("s2", parent_step_id="s1")
    assert g.nodes["s2"].parent_step_id == "s1"
    assert "s2" in g.nodes["s1"].children_ids
    assert g.nodes["s2"].status == StepStatus.RUNNING
    assert g.nodes["s2"].start_time is not None


def test_finish_step_records_end_time_and_status():
    g = ExecutionGraph("r1", "p", "1.0")
    g.add_root("s1", "agent_a")
    g.begin_step("s1")
    g.finish_step("s1", StepStatus.SUCCESS, output={"result": 42})
    node = g.nodes["s1"]
    assert node.status == StepStatus.SUCCESS
    assert node.output == {"result": 42}
    assert node.end_time is not None
    assert node.duration_ms() >= 0


def test_finish_step_records_error():
    g = ExecutionGraph("r1", "p", "1.0")
    g.add_root("s1", "agent_a")
    g.begin_step("s1")
    g.finish_step("s1", StepStatus.FAILED, error="boom")
    assert g.nodes["s1"].error == "boom"
    assert g.nodes["s1"].status == StepStatus.FAILED


def test_finish_step_unknown_raises():
    g = ExecutionGraph("r1", "p", "1.0")
    with pytest.raises(KeyError, match="inconnu"):
        g.finish_step("ghost", StepStatus.SUCCESS)


def test_stats_aggregates_by_status():
    g = ExecutionGraph("r1", "p", "1.0")
    g.add_root("s1", "a"); g.begin_step("s1"); g.finish_step("s1", StepStatus.SUCCESS)
    g.add_root("s2", "b"); g.begin_step("s2"); g.finish_step("s2", StepStatus.FAILED, error="x")
    g.add_root("s3", "c")  # pending
    stats = g.stats()
    assert stats["total_steps"] == 3
    assert stats["by_status"]["success"] == 1
    assert stats["by_status"]["failed"] == 1
    assert stats["by_status"]["pending"] == 1


def test_to_dict_serializable():
    g = ExecutionGraph("r1", "p", "1.0")
    g.add_root("s1", "a")
    g.begin_step("s1", parent_step_id=None)
    g.finish_step("s1", StepStatus.SUCCESS, output={"x": 1})
    d = g.to_dict()
    assert d["run_id"] == "r1"
    assert "s1" in d["nodes"]
    assert d["nodes"]["s1"]["status"] == "success"


# ---------- DeterministicPlanner invariants ----------

def test_template_planner_passes_deterministic_assert():
    """Le TemplatePlanner par defaut respecte les invariants deterministes."""
    planner = TemplatePlanner()
    plan = planner.build("search_job_and_apply", {"user": {}})
    # Ne leve pas
    assert_deterministic_plan(plan.steps, plan.name, plan.version)
    # Tous les agents ont un nom
    assert all(s.agent_name for s in plan.steps)


def test_assert_deterministic_plan_rejects_non_list_steps():
    """Un plan avec steps en set/dict est refuse."""
    with pytest.raises(DeterministicPlannerError, match="doit etre une list"):
        assert_deterministic_plan(set(), "p", "1.0")


def test_assert_deterministic_plan_rejects_uuid_step_id():
    """Un step avec un step_id qui ressemble a un UUID est refuse (non-deterministe)."""
    bad_step = PlanStep(
        agent_name="x", depends_on=[], input_template={}, description="",
    )
    # On mock un step_id ressemblant a un UUID
    bad_step.step_id = "12345678-1234-1234-1234-123456789012"
    with pytest.raises(DeterministicPlannerError, match="UUID"):
        assert_deterministic_plan([bad_step], "p", "1.0")


def test_assert_deterministic_plan_accepts_distinct_agents_at_distinct_indices():
    """Steps avec meme agent_name mais index distincts : OK (pas de collision)."""
    s1 = PlanStep(agent_name="x", depends_on=[], input_template={}, description="")
    s2 = PlanStep(agent_name="x", depends_on=[], input_template={}, description="")
    # 2 steps distincts -> 2 step_ids derives differents (index 0 et 1)
    assert_deterministic_plan([s1, s2], "p", "1.0")  # ne leve pas


def test_assert_deterministic_plan_rejects_explicit_dup_step_id():
    """2 steps avec un meme step_id explicite non-derive sont refuses."""
    s1 = PlanStep(agent_name="x", depends_on=[], input_template={}, description="")
    s1.step_id = "shared-id"
    s2 = PlanStep(agent_name="y", depends_on=[], input_template={}, description="")
    s2.step_id = "shared-id"
    with pytest.raises(DeterministicPlannerError, match="doublon"):
        assert_deterministic_plan([s1, s2], "p", "1.0")


# ---------- Integration : graph live + causal graph ----------

@pytest.mark.asyncio
async def test_execution_graph_and_causal_graph_complement(tmp_path):
    """Live graph + causal graph : la live view est en memoire, l offline est reconstruit."""
    from omniagent.core.events.bus import Event, EventBus, EventType
    from omniagent.core.events.store import SqliteEventStore
    from omniagent.core.observability.causal import CausalGraph

    store = SqliteEventStore(str(tmp_path / "exec.db"))
    bus = EventBus(history_limit=100, store=store)
    corr = "exec-1"

    # Live graph
    g = ExecutionGraph(corr, "wf", "1.0")
    g.add_root("s1", "agent_a")
    g.begin_step("s1")
    await bus.publish(Event(
        type=EventType.AGENT_STARTED, payload={"agent": "a", "run_id": "r1"},
        source="a", correlation_id=corr,
    ))
    g.finish_step("s1", StepStatus.SUCCESS, output={"x": 1})
    await bus.publish(Event(
        type=EventType.AGENT_COMPLETED, payload={"agent": "a", "run_id": "r1"},
        source="a", correlation_id=corr,
    ))

    # Le live graph a 1 noeud
    assert g.stats()["total_steps"] == 1
    # Le causal graph reconstruit 2 events depuis le store
    cg = CausalGraph(bus=bus)
    trace = await cg.trace_run(corr)
    assert trace.total_events == 2
    # Les deux graphes sont complementaires (live detail + offline history)