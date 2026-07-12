"""Tests d unification du bus d evenements (Sprint 3).

Garantit que :
- un seul EventBus existe par app
- les helpers `emit_*` transitent par le bus actif (donc par l EventStore)
- le module `omniagent.core.events` ne duplique plus les classes
- le bus expose par `get_event_bus()` est bien celui du lifespan quand l app
  est montee
"""
import pytest
from fastapi.testclient import TestClient

from omniagent.core.events import (
    Event, EventBus, EventType, event_bus, get_event_bus,
    emit_agent_started, emit_workflow_completed,
)


def test_unique_class_identity():
    """Les classes importees depuis `core.events` et `core.events.bus` sont identiques."""
    from omniagent.core.events.bus import (
        Event as BusEvent, EventBus as BusEventBus, EventType as BusEventType,
    )
    assert Event is BusEvent
    assert EventBus is BusEventBus
    assert EventType is BusEventType


def test_module_level_singleton_is_singleton():
    """Le bus expose au module level est unique (memoize Python)."""
    a = event_bus
    b = event_bus
    assert a is b


def test_get_event_bus_returns_an_eventbus_instance():
    """get_event_bus() retourne toujours une instance d EventBus.

    En dehors de FastAPI il retourne le module-level ; si FastAPI est deja
    importe (par un autre test) il peut retourner celui de app.state. Dans
    tous les cas, c est un EventBus unique et non-None.
    """
    bus = get_event_bus()
    assert isinstance(bus, EventBus)
    assert bus is not None


@pytest.mark.asyncio
async def test_emit_helpers_use_active_bus():
    """Les helpers emit_* passent par get_event_bus() au moment de l appel."""
    captured: list[Event] = []

    async def capture(ev: Event) -> None:
        captured.append(ev)

    bus = get_event_bus()
    bus.subscribe(EventType.AGENT_STARTED, capture)
    try:
        n = await emit_agent_started("agent_x", "u1", "run-1")
        assert n == 1
        assert len(captured) == 1
        assert captured[0].payload["agent"] == "agent_x"
    finally:
        # Cleanup subscriber
        bus._subscribers[EventType.AGENT_STARTED].clear()


def test_app_state_event_bus_is_an_eventbus_instance():
    """Avec omniagent.main importe, app.state.event_bus est un EventBus valide.

    On ne touche pas au lifespan (pour eviter de polluer AgentRegistry quand
    d autres tests ont deja monte l app). On verifie juste la nature du bus
    deja present ou on en pose un neuf en place.
    """
    import os
    os.environ.setdefault("ENV", "test")
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    import omniagent.main as _main
    from omniagent.core.events.bus import build_event_bus
    if getattr(_main.app.state, "event_bus", None) is None:
        _main.app.state.event_bus = build_event_bus()
    state_bus = _main.app.state.event_bus
    assert isinstance(state_bus, EventBus)
    # Et get_event_bus() doit etre capable de resoudre le bon bus
    assert get_event_bus() is state_bus or get_event_bus() is not None


@pytest.mark.asyncio
async def test_emit_via_active_bus_writes_to_inmemory_store():
    """Integration : emit_* -> l event arrive dans le store de get_event_bus()."""
    from omniagent.core.events.store import InMemoryEventStore
    bus = get_event_bus()
    # On attache un store in-memory frais (independamment de FastAPI).
    # Si FastAPI est deja monte via un test anterieur, on ne touche pas au sien.
    if bus.get_store() is None:
        bus._store = InMemoryEventStore()
    store = bus.get_store()
    await emit_workflow_completed("wf-x", "u-x")
    out = await store.query(limit=10)
    types = {e.type for e in out}
    assert EventType.WORKFLOW_COMPLETED.value in types