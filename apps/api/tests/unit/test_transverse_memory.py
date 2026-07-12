"""Tests du Memory Agent."""
import pytest


@pytest.mark.asyncio
async def test_memory_remember_and_recall():
    from omniagent.agents.transverse.subagents.memory_agent import run
    r = await run({"action": "remember", "scope": "session", "key": "k1", "value": {"x": 1}}, "u1")
    assert r["stored"] is True
    r2 = await run({"action": "recall", "scope": "session", "key": "k1"}, "u1")
    assert r2["value"] == {"x": 1}


@pytest.mark.asyncio
async def test_memory_add_exclusion():
    from omniagent.agents.transverse.subagents.memory_agent import run
    from omniagent.agents.transverse.subagents.memory_agent import get_memory_agent
    agent = get_memory_agent()
    agent._memory.domain._store.clear()
    await run({"action": "add_exclusion", "contact_id": "c1", "reason": "candidate_recent"}, "u1")
    assert agent.is_excluded("c1", "candidate_recent")
    assert not agent.is_excluded("c1", "other_reason")


@pytest.mark.asyncio
async def test_memory_invalid_scope_returns_error():
    from omniagent.agents.transverse.subagents.memory_agent import run
    r = await run({"action": "remember", "scope": "invalid", "key": "k", "value": "v"}, "u1")
    assert "error" in r