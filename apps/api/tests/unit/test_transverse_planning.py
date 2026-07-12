"""Tests du Planning Agent."""
import pytest
from datetime import datetime, timedelta, timezone


@pytest.mark.asyncio
async def test_planning_schedule_and_tick():
    from omniagent.agents.transverse.subagents.planning_agent import get_planning_agent, run
    agent = get_planning_agent()
    agent._tasks.clear()

    # Tache qui doit tourner immediatement
    r = await run({"action": "schedule", "agent_name": "agent_x",
                   "payload": {"k": "v"}, "frequency": "daily",
                   "start_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()}, "u1")
    task_id = r["task_id"]
    assert r["scheduled"] is True

    due = await run({"action": "tick"}, "u1")
    assert any(d["task_id"] == task_id for d in due["due"])


@pytest.mark.asyncio
async def test_planning_list_for_user():
    from omniagent.agents.transverse.subagents.planning_agent import get_planning_agent, run
    agent = get_planning_agent()
    agent._tasks.clear()

    await run({"action": "schedule", "agent_name": "agent_a",
               "payload": {}, "frequency": "daily"}, "u1")
    await run({"action": "schedule", "agent_name": "agent_b",
               "payload": {}, "frequency": "weekly"}, "u1")
    r = await run({"action": "list"}, "u1")
    assert len(r["tasks"]) == 2
    assert {t["agent"] for t in r["tasks"]} == {"agent_a", "agent_b"}


@pytest.mark.asyncio
async def test_planning_cancel():
    from omniagent.agents.transverse.subagents.planning_agent import get_planning_agent, run
    agent = get_planning_agent()
    agent._tasks.clear()

    r = await run({"action": "schedule", "agent_name": "agent_c",
                   "payload": {}, "frequency": "daily"}, "u1")
    task_id = r["task_id"]
    cancel = await run({"action": "cancel", "task_id": task_id}, "u1")
    assert cancel["cancelled"] is True
    assert task_id not in agent._tasks