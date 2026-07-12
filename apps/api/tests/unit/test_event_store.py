"""Tests du store d evenements (InMemory + Sqlite)."""
import asyncio
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from omniagent.core.events.bus import Event, EventBus, EventType
from omniagent.core.events.store import (
    InMemoryEventStore, SqliteEventStore, StoredEvent,
)


def _make_event(type_: EventType, **kw) -> Event:
    return Event(
        type=type_,
        payload=kw.pop("payload", {}),
        source=kw.pop("source", "test"),
        user_id=kw.pop("user_id", None),
        correlation_id=kw.pop("correlation_id", None),
    )


# ---------- InMemoryEventStore ----------

@pytest.mark.asyncio
async def test_inmemory_append_and_query():
    store = InMemoryEventStore()
    e1 = _make_event(EventType.AGENT_STARTED, user_id="u1", payload={"a": 1})
    e2 = _make_event(EventType.AGENT_COMPLETED, user_id="u1", payload={"a": 2})
    e3 = _make_event(EventType.AGENT_FAILED, user_id="u2", payload={"a": 3})
    await store.append(e1, tenant_id="t1")
    await store.append(e2, tenant_id="t1")
    await store.append(e3, tenant_id="t2")

    out = await store.query()
    assert len(out) == 3

    out_u1 = await store.query(user_id="u1")
    assert len(out_u1) == 2
    assert {e.event_id for e in out_u1} == {e1.event_id, e2.event_id}

    out_t2 = await store.query(tenant_id="t2")
    assert len(out_t2) == 1
    assert out_t2[0].user_id == "u2"


@pytest.mark.asyncio
async def test_inmemory_history_limit_evicts_oldest():
    store = InMemoryEventStore(history_limit=2)
    e1 = _make_event(EventType.AGENT_STARTED, user_id="u1")
    e2 = _make_event(EventType.AGENT_STARTED, user_id="u1")
    e3 = _make_event(EventType.AGENT_STARTED, user_id="u1")
    await store.append(e1)
    await store.append(e2)
    await store.append(e3)
    out = await store.query()
    assert [e.event_id for e in out] == [e2.event_id, e3.event_id]


@pytest.mark.asyncio
async def test_inmemory_query_by_correlation_id():
    store = InMemoryEventStore()
    e1 = _make_event(EventType.AGENT_STARTED, correlation_id="run-42")
    e2 = _make_event(EventType.AGENT_COMPLETED, correlation_id="run-42")
    e3 = _make_event(EventType.AGENT_COMPLETED, correlation_id="run-43")
    await store.append(e1)
    await store.append(e2)
    await store.append(e3)
    out = await store.query(correlation_id="run-42")
    assert {e.event_id for e in out} == {e1.event_id, e2.event_id}


# ---------- SqliteEventStore ----------

@pytest.fixture
def sqlite_path(tmp_path):
    # Pas de cleanup explicite : pytest tmp_path est gere par le framework
    # et SQLite sur Windows peut garder un lock bref qui fait echouer unlink().
    return str(tmp_path / "events.db")


@pytest.mark.asyncio
async def test_sqlite_append_and_query(sqlite_path):
    store = SqliteEventStore(sqlite_path)
    e1 = _make_event(EventType.AGENT_STARTED, user_id="u1", payload={"a": 1})
    e2 = _make_event(EventType.AGENT_COMPLETED, user_id="u1", payload={"a": 2})
    await store.append(e1, tenant_id="t1")
    await store.append(e2, tenant_id="t1")
    out = await store.query()
    assert len(out) == 2
    # Payload roundtrip
    payload_values = {e.payload["a"] for e in out}
    assert payload_values == {1, 2}


@pytest.mark.asyncio
async def test_sqlite_survives_reopen(sqlite_path):
    """Le store SQLite doit retrouver les events apres fermeture+reouverture."""
    store1 = SqliteEventStore(sqlite_path)
    e1 = _make_event(EventType.WORKFLOW_STARTED, user_id="u1")
    await store1.append(e1, tenant_id="t1")
    await store1.close()

    # Reouverture : on doit retrouver e1
    store2 = SqliteEventStore(sqlite_path)
    out = await store2.query()
    assert len(out) == 1
    assert out[0].event_id == e1.event_id
    assert out[0].type == EventType.WORKFLOW_STARTED.value


@pytest.mark.asyncio
async def test_sqlite_idempotent_on_duplicate_event_id(sqlite_path):
    """Un meme event_id appende 2x ne cree pas de doublon (replay-safe)."""
    store = SqliteEventStore(sqlite_path)
    e1 = _make_event(EventType.AGENT_STARTED, user_id="u1")
    await store.append(e1)
    await store.append(e1)  # meme event_id
    out = await store.query()
    assert len(out) == 1


@pytest.mark.asyncio
async def test_sqlite_filter_by_type_and_user_and_tenant(sqlite_path):
    store = SqliteEventStore(sqlite_path)
    await store.append(_make_event(EventType.AGENT_STARTED, user_id="u1"), tenant_id="t1")
    await store.append(_make_event(EventType.AGENT_COMPLETED, user_id="u1"), tenant_id="t1")
    await store.append(_make_event(EventType.AGENT_FAILED, user_id="u2"), tenant_id="t2")
    out = await store.query(event_type=EventType.AGENT_STARTED.value, user_id="u1", tenant_id="t1")
    assert len(out) == 1


@pytest.mark.asyncio
async def test_sqlite_filter_since(sqlite_path):
    store = SqliteEventStore(sqlite_path)
    now = datetime.now(timezone.utc)
    # On insere 3 events avec des timestamps controles en re-write
    e1 = _make_event(EventType.AGENT_STARTED, user_id="u1")
    e2 = _make_event(EventType.AGENT_STARTED, user_id="u1")
    e3 = _make_event(EventType.AGENT_STARTED, user_id="u1")
    await store.append(e1)
    await store.append(e2)
    await store.append(e3)
    # since=now+1h : aucun event visible
    future = now + timedelta(hours=1)
    out = await store.query(since=future)
    assert out == []


# ---------- Integration avec EventBus ----------

@pytest.mark.asyncio
async def test_event_bus_persists_to_inmemory_store():
    store = InMemoryEventStore()
    bus = EventBus(history_limit=10, store=store)
    e1 = _make_event(EventType.AGENT_STARTED, user_id="u1", payload={"k": "v"})
    await bus.publish(e1)
    out = await store.query()
    assert len(out) == 1
    assert out[0].event_id == e1.event_id
    # Les subscribers (in-memory fan-out) continuent de marcher
    received = []
    bus.subscribe(EventType.AGENT_STARTED, lambda ev: received.append(ev))
    await bus.publish(_make_event(EventType.AGENT_STARTED, user_id="u1"))
    assert len(received) == 1


@pytest.mark.asyncio
async def test_event_bus_persists_to_sqlite_with_tenant_context(sqlite_path):
    store = SqliteEventStore(sqlite_path)
    bus = EventBus(history_limit=10, store=store)
    bus.set_tenant_context(tenant_id="org-99")
    await bus.publish(_make_event(EventType.AGENT_STARTED, user_id="u1"))
    out = await store.query(tenant_id="org-99")
    assert len(out) == 1
    assert out[0].tenant_id == "org-99"


@pytest.mark.asyncio
async def test_event_bus_store_failure_does_not_break_publish():
    """Si le store leve, l event doit quand meme etre delivre aux subscribers."""
    class BrokenStore:
        async def append(self, event, tenant_id=None):
            raise RuntimeError("store down")
        async def query(self, **kw):
            return []
        async def close(self):
            pass

    bus = EventBus(history_limit=10, store=BrokenStore())
    received = []
    bus.subscribe(EventType.AGENT_STARTED, lambda ev: received.append(ev))
    # Ne doit pas lever
    await bus.publish(_make_event(EventType.AGENT_STARTED, user_id="u1"))
    # Le subscriber a recu l event malgre le store en panne
    assert len(received) == 1
    # L event est parti en DLQ (au moins 1 entree, on ne compte pas le subscriber)
    assert len(bus.get_dlq()) >= 1