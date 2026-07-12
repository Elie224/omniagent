"""Tests du branchement circuit breaker dans MultiSourceBackend."""
import pytest

from omniagent.agents.emploi.job_search import (
    JobOffer, MultiSourceBackend,
)
from omniagent.connectors.manager import connector_manager
from omniagent.core.resilience.circuit_breaker import (
    CircuitBreakerConfig, circuit_breaker_registry,
)


class _Boom:
    """Backend qui leve systematiquement une exception."""
    def __init__(self, name, exc=RuntimeError("down")):
        self.name = name
        self._exc = exc

    async def search(self, criteria):
        raise self._exc


class _OK:
    def __init__(self, name, count=1):
        self.name = name
        self._count = count

    async def search(self, criteria):
        return [
            JobOffer(
                id=f"{self.name}_{i}", title=f"job {i}", company="X",
                location="Paris", contract="alternance",
                url=f"https://{self.name}.example/{i}",
                posted_at="2026-07-01", description="d", source=self.name,
            )
            for i in range(self._count)
        ]


@pytest.fixture
def fresh_breakers():
    """Reset tous les breakers avant chaque test pour eviter les fuites d etat."""
    for b in circuit_breaker_registry.all():
        circuit_breaker_registry.reset(b.name)
    yield
    for b in circuit_breaker_registry.all():
        circuit_breaker_registry.reset(b.name)


@pytest.mark.asyncio
async def test_breaker_opens_after_threshold_failures(fresh_breakers):
    """Apres N echecs consecutifs, le breaker s ouvre et rejette instantanement."""
    cfg = CircuitBreakerConfig(failure_threshold=3, reset_timeout_s=60.0)
    connector_manager._breakers.get("test_boom_a", cfg)  # pre-create

    multi = MultiSourceBackend(
        [_Boom("test_boom_a"), _OK("test_ok_b", 1)],
        name="breaker_test_1",
        use_breaker=True,
    )
    for _ in range(3):
        await multi.search({})
    out = await multi.search({})
    assert len(out) == 1
    assert out[0].source == "test_ok_b"
    assert "test_boom_a" in multi.last_errors
    assert "circuit_open" in multi.last_errors["test_boom_a"]


@pytest.mark.asyncio
async def test_breaker_uses_source_name_as_identifier(fresh_breakers):
    """Le breaker est indexe par backend.name, pas par le nom du multi."""
    multi = MultiSourceBackend(
        [_Boom("src_x"), _OK("src_y", 2)],
        name="my_multi",
        use_breaker=True,
    )
    for _ in range(6):
        await multi.search({})
    breaker = connector_manager.breaker("src_x")
    snap = breaker.snapshot()
    assert snap["state"] == "open"
    snap_y = connector_manager.breaker("src_y").snapshot()
    assert snap_y["state"] == "closed"


@pytest.mark.asyncio
async def test_fallback_uses_breaker_in_jobsearcher(fresh_breakers):
    """JobSearcher(backend=fallback) cable bien le breaker."""
    from omniagent.agents.emploi.job_search import JobSearcher
    searcher = JobSearcher(browser=None, user_profile={}, backend="fallback")
    out = await searcher.search({"keywords": "data", "max_results": 3})
    assert len(out) == 3
    assert all(o.source == "linkedin" for o in out)