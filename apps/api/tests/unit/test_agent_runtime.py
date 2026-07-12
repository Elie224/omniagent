"""Tests du runtime agent (context isolation, sandbox, lifecycle)."""
import pytest


def test_isolated_context_seal():
    from omniagent.agents.runtime.context.isolation import IsolatedContext
    ctx = IsolatedContext(agent_name="a")
    ctx.grant_secret("k", "v")
    ctx.seal()
    try:
        ctx.grant_secret("k2", "v2")
    except RuntimeError:
        return
    raise AssertionError("Aurait du lever RuntimeError")


def test_isolated_context_fork_is_independent():
    from omniagent.agents.runtime.context.isolation import IsolatedContext
    ctx = IsolatedContext(agent_name="a", input={"x": 1})
    fork = ctx.fork()
    fork.input["x"] = 2
    assert ctx.input["x"] == 1
    assert fork.input["x"] == 2


def test_context_pool_acquire_release():
    from omniagent.agents.runtime.context.isolation import context_pool
    ctx = context_pool.acquire(agent_name="a")
    assert ctx.context_id in context_pool._active
    context_pool.release(ctx.context_id)
    assert ctx.context_id not in context_pool._active


def test_context_pool_max_active():
    from omniagent.agents.runtime.context.isolation import ContextPool
    pool = ContextPool(max_active=2)
    a = pool.acquire()
    b = pool.acquire()
    try:
        c = pool.acquire()
    except RuntimeError:
        return
    raise AssertionError("Aurait du lever RuntimeError")


@pytest.mark.asyncio
async def test_lifecycle_create_start_stop():
    from omniagent.agents.runtime.lifecycle.manager import lifecycle_manager
    inst = await lifecycle_manager.create("agent_x")
    assert inst.state.value == "created"
    await lifecycle_manager.start(inst.instance_id)
    assert inst.state.value == "running"
    await lifecycle_manager.stop(inst.instance_id)
    assert inst.state.value == "stopped"


@pytest.mark.asyncio
async def test_lifecycle_hooks_called():
    from omniagent.agents.runtime.lifecycle.manager import (
        lifecycle_manager, LifecycleHooks,
    )
    called = []
    hooks = LifecycleHooks(
        on_start=lambda: called.append("start") or _noop_async(),
        on_stop=lambda: called.append("stop") or _noop_async(),
    )
    inst = await lifecycle_manager.create("agent_x", hooks=hooks)
    await lifecycle_manager.start(inst.instance_id)
    await lifecycle_manager.stop(inst.instance_id)
    assert "start" in called
    assert "stop" in called


async def _noop_async():
    return None


@pytest.mark.asyncio
async def test_sandbox_runtime_tool_call_limit():
    from omniagent.agents.runtime.sandbox.sandbox import (
        AgentSandbox, SandboxLimits, SandboxViolation,
    )
    sb = AgentSandbox(SandboxLimits(max_tool_calls=2))
    with sb.run("a"):
        sb.check_tool_call()
        sb.check_tool_call()
        try:
            sb.check_tool_call()
        except SandboxViolation:
            return
    raise AssertionError("Aurait du lever SandboxViolation")