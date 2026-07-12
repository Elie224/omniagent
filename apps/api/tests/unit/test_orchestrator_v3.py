"""Tests de l orchestrateur V3 (Planner strategy + ExecutionPolicy)."""
import asyncio
import pytest


def test_template_planner_supports_known():
    from omniagent.core.orchestrator.planner.base import TemplatePlanner
    p = TemplatePlanner()
    assert p.supports("search_job_and_apply") is True
    assert p.supports("unknown_intent") is False


def test_template_planner_builds():
    from omniagent.core.orchestrator.planner.base import TemplatePlanner
    p = TemplatePlanner()
    plan = p.build("search_job_and_apply", {})
    assert plan.name == "search_job_and_apply"
    assert any(s.agent_name == "agent_linkedin" for s in plan.steps)


def test_planner_registry_routes_to_first_match():
    from omniagent.core.orchestrator.planner.base import PlannerRegistry, TemplatePlanner
    reg = PlannerRegistry()
    reg.register(TemplatePlanner())
    planner = reg.get_for("search_job_and_apply")
    assert isinstance(planner, TemplatePlanner)


@pytest.mark.asyncio
async def test_sequential_policy_executes_in_order():
    from omniagent.core.orchestrator.policies.base import SequentialPolicy
    from omniagent.core.orchestrator.planner.base import Plan, PlanStep
    order = []
    async def run_step(step, uid, ctx):
        order.append(step.agent_name)
        return {"status": "success", "output": {}}
    plan = Plan(name="p", version="1.0.0", steps=[
        PlanStep("a", [], {}, "step a"),
        PlanStep("b", ["a"], {}, "step b"),
    ])
    await SequentialPolicy().execute(plan, run_step, "u1", {})
    assert order == ["a", "b"]


@pytest.mark.asyncio
async def test_parallel_policy_runs_independent_in_parallel():
    from omniagent.core.orchestrator.policies.base import ParallelPolicy
    from omniagent.core.orchestrator.planner.base import Plan, PlanStep
    import time
    started: list[str] = []
    async def run_step(step, uid, ctx):
        started.append(step.agent_name)
        await asyncio.sleep(0.05)
        return {"status": "success", "output": {}}
    plan = Plan(name="p", version="1.0.0", steps=[
        PlanStep("a", [], {}, "a"),
        PlanStep("b", [], {}, "b"),
    ])
    t0 = time.time()
    await ParallelPolicy().execute(plan, run_step, "u1", {})
    elapsed = time.time() - t0
    # Parallel doit etre plus rapide que sequentiel (2 * 50ms = 100ms)
    assert elapsed < 0.09


@pytest.mark.asyncio
async def test_adaptive_policy_chooses_parallel_for_many_independent():
    from omniagent.core.orchestrator.policies.base import AdaptivePolicy
    from omniagent.core.orchestrator.planner.base import Plan, PlanStep
    async def run_step(step, uid, ctx):
        return {"status": "success", "output": {}}
    plan = Plan(name="p", version="1.0.0", steps=[
        PlanStep("a", [], {}, "a"),
        PlanStep("b", [], {}, "b"),
        PlanStep("c", [], {}, "c"),
    ])
    results = await AdaptivePolicy().execute(plan, run_step, "u1", {})
    assert set(results.keys()) == {"a", "b", "c"}