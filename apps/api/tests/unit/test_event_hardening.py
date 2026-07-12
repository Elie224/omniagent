"""Tests des 3 chantiers stabilisation (Sprint 3+) :
- AgentRegistry idempotence
- Pydantic event payload schema
- EventBus dedupe window
"""
import asyncio
import warnings

import pytest

from omniagent.core.events.bus import Event, EventBus, EventType
from omniagent.core.events.schema import (
    PAYLOAD_SCHEMAS, EventValidationWarning, validate_payload,
)
from omniagent.core.registry.agent_registry import AgentRegistry, AgentSpec


# ---------- AgentRegistry idempotence ----------

def test_agent_registry_register_is_idempotent():
    reg = AgentRegistry()
    spec = AgentSpec(
        name="agent_x", module="test", role="specialiste",
        description="x", run_fn=lambda: None, dependencies=[],
    )
    reg.register(spec)
    # Re-register doit etre un no-op, pas une ValueError
    reg.register(spec)
    assert reg.get("agent_x") is spec


def test_agent_registry_register_does_not_overwrite_existing():
    reg = AgentRegistry()
    spec_a = AgentSpec(name="x", module="a", role="r", description="",
                        run_fn=lambda: None, dependencies=[])
    spec_b = AgentSpec(name="x", module="b", role="r", description="",
                        run_fn=lambda: None, dependencies=[])
    reg.register(spec_a)
    reg.register(spec_b)
    # Le premier enregistrement gagne (defense contre l ecrasement accidentel)
    assert reg.get("x") is spec_a


# ---------- Pydantic event schema ----------

def test_validate_payload_known_type_valid():
    payload = {"agent": "data_analyst", "run_id": "r-1"}
    out, ok = validate_payload("agent.started", payload)
    assert ok is True
    assert out["agent"] == "data_analyst"


def test_validate_payload_known_type_invalid_falls_back_to_raw():
    """Un payload qui ne matche pas le schema : warning + payload raw."""
    payload = {"agent": 12345, "run_id": None}  # types incorrects
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", EventValidationWarning)
        out, ok = validate_payload("agent.started", payload)
    assert ok is False
    assert out == payload  # on garde le payload brut
    assert any(issubclass(w.category, EventValidationWarning) for w in caught)


def test_validate_payload_unknown_type_passes_through():
    """Un type sans schema : on accepte en silence."""
    payload = {"anything": "goes"}
    out, ok = validate_payload("custom.event", payload)
    assert ok is True
    assert out == payload


def test_all_known_event_types_have_a_schema():
    """Tous les EventType de l enum ont leur schema (anti-regression)."""
    for ev_type in EventType:
        assert ev_type.value in PAYLOAD_SCHEMAS, (
            f"Missing schema for {ev_type.value!r}"
        )


# ---------- EventBus dedupe window ----------

@pytest.mark.asyncio
async def test_publish_with_dedupe_skips_duplicate_event_id():
    bus = EventBus(history_limit=10, dedupe_window=100)
    received = []

    async def sub(ev):
        received.append(ev)
    bus.subscribe(EventType.AGENT_STARTED, sub)

    e = Event(
        type=EventType.AGENT_STARTED,
        payload={"agent": "x", "run_id": "r1"},
        source="test", event_id="fixed-id-1",
    )
    n1 = await bus.publish(e)
    # 2e publish avec meme event_id : ignore
    n2 = await bus.publish(e)
    assert n1 >= 0
    assert n2 == 0
    assert len(received) == 1


@pytest.mark.asyncio
async def test_publish_without_dedupe_replays_subscribers():
    """Si dedupe_window=0, pas de dedupe : chaque publish() notifie."""
    bus = EventBus(history_limit=10, dedupe_window=0)
    received = []
    bus.subscribe(EventType.AGENT_STARTED, lambda ev: received.append(ev))
    e = Event(
        type=EventType.AGENT_STARTED,
        payload={"agent": "x", "run_id": "r1"},
        source="test", event_id="fixed-id-2",
    )
    await bus.publish(e)
    await bus.publish(e)
    assert len(received) == 2


@pytest.mark.asyncio
async def test_publish_dedupe_does_not_grow_unbounded():
    """Au-dela de dedupe_window, le set est GC (FIFO simplifie)."""
    bus = EventBus(history_limit=10, dedupe_window=4)
    for i in range(20):
        await bus.publish(Event(
            type=EventType.AGENT_STARTED,
            payload={"agent": "x", "run_id": f"r{i}"},
            source="test", event_id=f"id-{i}",
        ))
    # Le set interne ne doit pas depasser dedupe_window (apres GC)
    assert len(bus._seen_event_ids) <= bus._dedupe_window


@pytest.mark.asyncio
async def test_publish_validates_payload_against_schema():
    """Un payload invalide log un warning et l event transite quand meme."""
    bus = EventBus(history_limit=10, dedupe_window=0)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", EventValidationWarning)
        e = Event(
            type=EventType.AGENT_STARTED,
            payload={"agent": 12345, "run_id": None},  # types faux
            source="test",
        )
        n = await bus.publish(e)
    # L event passe quand meme (fail-soft)
    assert n == 0  # pas de subscriber, donc 0 handler reussi
    assert any(issubclass(w.category, EventValidationWarning) for w in caught)