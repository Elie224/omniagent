"""Tests du Monitoring Agent."""
import pytest


@pytest.mark.asyncio
async def test_monitoring_record_and_error_rate():
    from omniagent.agents.transverse.subagents.monitoring_agent import get_monitoring_agent, run
    agent = get_monitoring_agent()
    agent._runs.clear()

    # 2 success, 3 failed -> rate 60% > seuil 50%
    for i in range(2):
        await run({"action": "record", "agent_name": "agent_test", "status": "success",
                   "run_id": f"ok{i}"}, "u1")
    for i in range(3):
        await run({"action": "record", "agent_name": "agent_test", "status": "failed",
                   "run_id": f"ko{i}", "error": "boom"}, "u1")

    r = await run({"action": "error_rate", "agent_name": "agent_test"}, "u1")
    assert r["total"] == 5
    assert r["errors"] == 3
    assert r["rate"] == 0.6
    assert r["alert"] is True


@pytest.mark.asyncio
async def test_monitoring_snapshot_lists_agents():
    from omniagent.agents.transverse.subagents.monitoring_agent import get_monitoring_agent, run
    agent = get_monitoring_agent()
    agent._runs.clear()

    await run({"action": "record", "agent_name": "agent_a", "status": "success",
               "run_id": "1"}, "u1")
    await run({"action": "record", "agent_name": "agent_b", "status": "failed",
               "run_id": "2", "error": "x"}, "u1")

    r = await run({"action": "snapshot"}, "u1")
    assert "agent_a" in r["snapshot"]
    assert "agent_b" in r["snapshot"]


@pytest.mark.asyncio
async def test_monitoring_zombies_detection():
    from omniagent.agents.transverse.subagents.monitoring_agent import get_monitoring_agent, run
    agent = get_monitoring_agent()
    agent._runs.clear()

    # 4 runs "running" -> zombie
    for i in range(4):
        await run({"action": "record", "agent_name": "agent_stuck",
                   "status": "running", "run_id": f"r{i}"}, "u1")

    r = await run({"action": "zombies"}, "u1")
    assert "agent_stuck" in r["zombies"]