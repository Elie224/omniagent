"""Tests du Reliability Sprint (replay + versioning + observability validator)."""
import asyncio
from datetime import datetime, timezone, timedelta

import pytest

from omniagent.core.events.bus import Event, EventBus, EventType
from omniagent.core.events.replay import (
    ReplayResult, replay, replay_into_bus, _stored_to_event,
)
from omniagent.core.events.schema import (
    CURRENT_SCHEMA_VERSION, MIGRATIONS, migrate_payload, register_migration,
)
from omniagent.core.events.store import InMemoryEventStore, SqliteEventStore
from omniagent.core.observability.validator import (
    ValidationIssue, validate_observability_consistency,
)


# ---------- Replay engine ----------

@pytest.mark.asyncio
async def test_replay_dry_run_counts_events_without_callback(tmp_path):
    """En dry_run, on scanne le store et on retourne le count, sans appeler into."""
    store = SqliteEventStore(str(tmp_path / "replay.db"))
    bus = EventBus(history_limit=10, store=store)
    for i in range(3):
        await bus.publish(Event(
            type=EventType.AGENT_STARTED,
            payload={"agent": "x", "run_id": f"r{i}"},
            source="test", correlation_id="run-A",
        ))
    called = []
    async def cb(ev):
        called.append(ev)
    res = await replay(bus, correlation_id="run-A", into=cb, dry_run=True)
    assert res.events_scanned == 3
    assert res.events_replayed == 3
    # dry_run=True : on n appelle PAS le callback
    assert called == []


@pytest.mark.asyncio
async def test_replay_with_callback_invokes_into(tmp_path):
    store = SqliteEventStore(str(tmp_path / "replay2.db"))
    bus = EventBus(history_limit=10, store=store)
    for i in range(2):
        await bus.publish(Event(
            type=EventType.AGENT_COMPLETED,
            payload={"agent": "x", "run_id": f"r{i}"},
            source="test", correlation_id="run-B",
        ))
    received = []
    async def cb(ev):
        received.append(ev)
    res = await replay(bus, correlation_id="run-B", into=cb, dry_run=False)
    assert res.events_replayed == 2
    assert len(received) == 2


@pytest.mark.asyncio
async def test_replay_filters_by_event_type(tmp_path):
    store = SqliteEventStore(str(tmp_path / "replay3.db"))
    bus = EventBus(history_limit=10, store=store)
    await bus.publish(Event(
        type=EventType.AGENT_STARTED,
        payload={"agent": "x", "run_id": "r1"},
        source="t", correlation_id="run-C",
    ))
    await bus.publish(Event(
        type=EventType.WORKFLOW_COMPLETED,
        payload={"workflow_id": "w1"},
        source="t", correlation_id="run-C",
    ))
    received = []
    async def cb(ev):
        received.append(ev)
    res = await replay(
        bus, correlation_id="run-C",
        event_type=EventType.WORKFLOW_COMPLETED, into=cb, dry_run=False,
    )
    assert res.events_replayed == 1
    assert received[0].type == EventType.WORKFLOW_COMPLETED


@pytest.mark.asyncio
async def test_replay_without_store_returns_error():
    bus = EventBus(history_limit=10, store=None)
    res = await replay(bus, into=lambda ev: None)
    assert res.events_scanned == 0
    assert "non initialise" in res.errors[0]


@pytest.mark.asyncio
async def test_replay_into_bus_is_dedup_safe(tmp_path):
    """replay_into_bus avec dedupe active : le 2e pass est dedupe par event_id."""
    store = SqliteEventStore(str(tmp_path / "replay4.db"))
    bus_a = EventBus(history_limit=10, store=store, dedupe_window=100)
    bus_b = EventBus(history_limit=10, store=store, dedupe_window=100)
    # Publication initiale
    await bus_a.publish(Event(
        type=EventType.AGENT_STARTED,
        payload={"agent": "x", "run_id": "r1"},
        source="t", event_id="fixed-1",
    ))
    # Replay dans un autre bus (meme dedupe, meme store -> ignore)
    res = await replay_into_bus(
        bus_a, correlation_id=None,
        target_bus=bus_b, dry_run=False,
    )
    # bus_b a le meme dedupe : 0 nouveau handler reussi car event_id vu
    # (mais dry_run=False, donc on a tente)
    assert res.events_replayed == 1


def test_stored_to_event_roundtrip(tmp_path):
    """StoredEvent -> Event preserve les champs metier."""
    from omniagent.core.events.store import StoredEvent
    stored = StoredEvent(
        event_id="e1", type="agent.started", source="t",
        timestamp="2026-07-05T08:00:00+00:00",
        payload={"agent": "x", "run_id": "r1"},
        correlation_id="c1", causation_id=None,
        user_id="u1", tenant_id="t1",
    )
    ev = _stored_to_event(stored)
    assert ev.event_id == "e1"
    assert ev.type == EventType.AGENT_STARTED
    assert ev.correlation_id == "c1"
    assert ev.user_id == "u1"


# ---------- Versioning / migrations ----------

def test_migrate_payload_no_migration_returns_as_is():
    out, v = migrate_payload("agent.started", {"agent": "x", "run_id": "r1"}, 1)
    assert v == 1
    assert out["agent"] == "x"


def test_register_migration_chains_to_current_version():
    # On simule l evolution d un payload : v1 -> v2 -> v3 (current=3)
    CURRENT_SCHEMA_VERSION["agent.completed"] = 3

    def v1_to_v2(p):
        return {**p, "duration_ms": 0.0}

    def v2_to_v3(p):
        return {**p, "cost_usd": 0.0}

    register_migration("agent.completed", 1, v1_to_v2)
    register_migration("agent.completed", 2, v2_to_v3)

    out, v = migrate_payload("agent.completed", {"agent": "x", "run_id": "r1"}, 1)
    assert v == 3
    assert out["duration_ms"] == 0.0
    assert out["cost_usd"] == 0.0

    # Cleanup
    del MIGRATIONS["agent.completed"]
    CURRENT_SCHEMA_VERSION["agent.completed"] = 1


def test_migrate_payload_stops_at_missing_step():
    CURRENT_SCHEMA_VERSION["agent.failed"] = 3
    register_migration("agent.failed", 1, lambda p: {**p, "v2_field": True})
    # Pas de migration v2 -> v3 : on s arrete a v2
    out, v = migrate_payload("agent.failed", {"agent": "x", "run_id": "r1"}, 1)
    assert v == 2
    assert out["v2_field"] is True
    del MIGRATIONS["agent.failed"]
    CURRENT_SCHEMA_VERSION["agent.failed"] = 1


def test_migrate_payload_handles_broken_migration():
    CURRENT_SCHEMA_VERSION["workflow.started"] = 2
    def broken(p):
        raise ValueError("boom")
    register_migration("workflow.started", 1, broken)
    out, v = migrate_payload("workflow.started", {"workflow_id": "w1"}, 1)
    # Migration cassee : on garde le payload tel quel
    assert v == 1
    assert out["workflow_id"] == "w1"
    del MIGRATIONS["workflow.started"]
    CURRENT_SCHEMA_VERSION["workflow.started"] = 1


# ---------- Observability validator ----------

@pytest.mark.asyncio
async def test_validator_clean_when_balanced():
    bus = EventBus(history_limit=100, store=InMemoryEventStore())
    # Publie des events equilibres (chaque started a un completed ou failed)
    for i in range(4):
        await bus.publish(Event(
            type=EventType.AGENT_STARTED,
            payload={"agent": "x", "run_id": f"r{i}"},
            source="t", user_id="u1",
        ))
    for i in range(2):
        await bus.publish(Event(
            type=EventType.AGENT_COMPLETED,
            payload={"agent": "x", "run_id": f"r{i}"},
            source="t", user_id="u1",
        ))
    for i in range(2, 4):
        await bus.publish(Event(
            type=EventType.AGENT_FAILED,
            payload={"agent": "x", "run_id": f"r{i}", "error": "x", "retryable": False},
            source="t", user_id="u1",
        ))
    issues = validate_observability_consistency(bus=bus)
    # Pas d unresolved : 0 issue
    assert all(i.code != "high_unresolved_runs" for i in issues)


@pytest.mark.asyncio
async def test_validator_detects_high_unresolved_runs():
    bus = EventBus(history_limit=100, store=InMemoryEventStore())
    # 10 started, 1 completed => 90% unresolved
    for i in range(10):
        await bus.publish(Event(
            type=EventType.AGENT_STARTED,
            payload={"agent": "x", "run_id": f"r{i}"},
            source="t", user_id="u1",
        ))
    await bus.publish(Event(
        type=EventType.AGENT_COMPLETED,
        payload={"agent": "x", "run_id": "r0"},
        source="t", user_id="u1",
    ))
    issues = validate_observability_consistency(bus=bus)
    assert any(i.code == "high_unresolved_runs" for i in issues)