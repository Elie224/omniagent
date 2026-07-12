"""Tests du sandbox d execution."""
import pytest
import time


def test_tool_call_limit():
    from omniagent.core.sandbox.sandbox import AgentSandbox, SandboxLimits, SandboxViolation
    sb = AgentSandbox(SandboxLimits(max_tool_calls=3))
    with sb.run("a"):
        for _ in range(3):
            sb.check_tool_call()
        try:
            sb.check_tool_call()
        except SandboxViolation:
            return
    raise AssertionError("Aurait du lever SandboxViolation")


def test_llm_cost_limit():
    from omniagent.core.sandbox.sandbox import AgentSandbox, SandboxLimits, SandboxViolation
    sb = AgentSandbox(SandboxLimits(max_llm_cost_usd=0.5))
    with sb.run("a"):
        sb.check_llm_cost(0.3)
        try:
            sb.check_llm_cost(0.3)
        except SandboxViolation:
            return
    raise AssertionError("Aurait du lever SandboxViolation")


def test_network_restriction():
    from omniagent.core.sandbox.sandbox import AgentSandbox, SandboxLimits, SandboxViolation
    sb = AgentSandbox(SandboxLimits(allowed_networks=["linkedin.com"]))
    sb.check_network("api.linkedin.com")
    try:
        sb.check_network("evil.com")
    except SandboxViolation:
        return
    raise AssertionError("Aurait du lever SandboxViolation")


def test_filesystem_restriction():
    from omniagent.core.sandbox.sandbox import AgentSandbox, SandboxLimits, SandboxViolation
    sb = AgentSandbox(SandboxLimits(allowed_filesystem_paths=["/data/"]))
    sb.check_filesystem("/data/file.pdf")
    try:
        sb.check_filesystem("/etc/passwd")
    except SandboxViolation:
        return
    raise AssertionError("Aurait du lever SandboxViolation")


def test_simulation_dry_run():
    from omniagent.core.sandbox.simulation import SimulationRunner
    runner = SimulationRunner(send_real=False)

    async def my_workflow(inputs, sim):
        sim.record_step("step1", {"value": inputs["x"] * 2})
        return {"status": "ok"}

    import asyncio
    sim = asyncio.run(runner.run(my_workflow, "wf", {"x": 5}))
    assert sim.finished_at is not None


def test_simulation_assert_pass():
    from omniagent.core.sandbox.simulation import SimulationRunner
    runner = SimulationRunner()

    async def my_workflow(inputs, sim):
        sim.record_step("step1", {"value": 10})
        return {"status": "ok"}

    import asyncio
    sim = asyncio.run(runner.run(my_workflow, "wf", {}, golden=[{"value": 10}]))
    assert sim.passed() is True
