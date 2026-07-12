"""Tests du Notification Agent."""
import pytest


@pytest.mark.asyncio
async def test_notification_send_in_app():
    from omniagent.agents.transverse.subagents.notification_agent import get_notification_agent, run
    agent = get_notification_agent()
    agent._history.clear()

    r = await run({"action": "send", "title": "Bienvenue", "body": "Hello",
                   "channel": "in_app", "priority": "normal"}, "u1")
    assert r["channel"] == "in_app"
    assert r["queued"] is True
    assert len(agent._history) == 1


@pytest.mark.asyncio
async def test_notification_send_email_queued():
    from omniagent.agents.transverse.subagents.notification_agent import run
    r = await run({"action": "send", "title": "Alerte", "body": "Facture en retard",
                   "channel": "email", "priority": "high"}, "u1")
    assert r["channel"] == "email"
    assert r["status"] == "queued"


@pytest.mark.asyncio
async def test_notification_bulk():
    from omniagent.agents.transverse.subagents.notification_agent import get_notification_agent, run
    agent = get_notification_agent()
    agent._history.clear()

    r = await run({"action": "bulk", "title": "Newsletter", "body": "Bla",
                   "user_ids": ["u1", "u2", "u3"], "channel": "in_app"}, "u1")
    assert len(r["results"]) == 3


@pytest.mark.asyncio
async def test_notification_history():
    from omniagent.agents.transverse.subagents.notification_agent import get_notification_agent, run
    agent = get_notification_agent()
    agent._history.clear()

    await run({"action": "send", "title": "A", "body": "B",
               "channel": "in_app"}, "u1")
    await run({"action": "send", "title": "C", "body": "D",
               "channel": "email"}, "u1")
    r = await run({"action": "history", "limit": 5}, "u1")
    assert len(r["history"]) == 2