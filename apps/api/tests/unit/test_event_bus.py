"""Tests de l Event Bus."""
import pytest
from omniagent.core.events.bus import event_bus, Event, EventType


@pytest.fixture(autouse=True)
def reset_bus():
    event_bus.clear()
    yield


@pytest.mark.asyncio
async def test_publish_and_subscribe():
    received = []
    async def handler(event):
        received.append(event.payload)
    event_bus.subscribe(EventType.AGENT_COMPLETED, handler)
    n = await event_bus.publish(Event(
        EventType.AGENT_COMPLETED, {"agent": "test", "result": "ok"},
        source="test", user_id="u1",
    ))
    assert n == 1
    assert received == [{"agent": "test", "result": "ok"}]


@pytest.mark.asyncio
async def test_history_filtered():
    await event_bus.publish(Event(EventType.AGENT_STARTED, {}, source="a", user_id="u1"))
    await event_bus.publish(Event(EventType.AGENT_COMPLETED, {}, source="a", user_id="u1"))
    await event_bus.publish(Event(EventType.AGENT_STARTED, {}, source="a", user_id="u2"))
    history = event_bus.get_history(event_type=EventType.AGENT_STARTED)
    assert len(history) == 2
    history_u1 = event_bus.get_history(user_id="u1")
    assert len(history_u1) == 2  # u1 a 2 events : AGENT_STARTED + AGENT_COMPLETED


@pytest.mark.asyncio
async def test_failed_handler_goes_to_dlq():
    async def broken(event):
        raise RuntimeError("boom")
    event_bus.subscribe(EventType.AGENT_FAILED, broken)
    n = await event_bus.publish(Event(EventType.AGENT_FAILED, {}, source="a"))
    assert n == 0
    assert len(event_bus.get_dlq()) == 1


@pytest.mark.asyncio
async def test_unsubscribe():
    received = []
    async def handler(event):
        received.append(event)
    unsub = event_bus.subscribe(EventType.MEMORY_UPDATED, handler)
    await event_bus.publish(Event(EventType.MEMORY_UPDATED, {}, source="a"))
    unsub()
    await event_bus.publish(Event(EventType.MEMORY_UPDATED, {}, source="a"))
    assert len(received) == 1