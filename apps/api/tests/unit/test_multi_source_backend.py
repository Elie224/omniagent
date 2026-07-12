"""Tests du MultiSourceBackend (fallback sequentiel entre sources)."""
import pytest

from omniagent.agents.emploi.job_search import (
    JobOffer, MultiSourceBackend, MockBackend,
)


class _Boom:
    """Backend qui leve systematiquement une exception."""
    def __init__(self, name, exc=RuntimeError("down")):
        self.name = name
        self._exc = exc

    async def search(self, criteria):
        raise self._exc


class _Empty:
    """Backend qui retourne toujours une liste vide."""
    def __init__(self, name):
        self.name = name

    async def search(self, criteria):
        return []


class _OK:
    """Backend qui retourne une offre pour la source demandee."""
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


@pytest.mark.asyncio
async def test_first_source_wins_when_it_returns_results():
    """Si la 1ere source retourne des offres, on ne consulte pas les suivantes."""
    multi = MultiSourceBackend([_OK("a", 2), _OK("b", 5)], name="test")
    out = await multi.search({})
    assert len(out) == 2
    assert all(o.source == "a" for o in out)
    assert multi.last_errors == {}


@pytest.mark.asyncio
async def test_falls_back_on_exception():
    """Si la 1ere source leve, on tente la 2e."""
    multi = MultiSourceBackend(
        [_Boom("a"), _OK("b", 3), _OK("c", 10)],
        name="test",
    )
    out = await multi.search({})
    assert len(out) == 3
    assert all(o.source == "b" for o in out)
    # L erreur de "a" est tracee
    assert "a" in multi.last_errors
    assert "RuntimeError" in multi.last_errors["a"]
    # "b" n a pas d erreur (elle a reussi)
    assert "b" not in multi.last_errors


@pytest.mark.asyncio
async def test_falls_back_on_empty_result():
    """Si la 1ere source retourne [], on tente la suivante."""
    multi = MultiSourceBackend(
        [_Empty("a"), _OK("b", 4)],
        name="test",
    )
    out = await multi.search({})
    assert len(out) == 4
    assert all(o.source == "b" for o in out)
    assert multi.last_errors.get("a") == "empty_result"


@pytest.mark.asyncio
async def test_all_sources_fail_returns_empty_and_records_errors():
    """Si tout explose, on remonte [] et on garde la trace des erreurs."""
    multi = MultiSourceBackend(
        [_Boom("a"), _Boom("b"), _Boom("c", exc=ValueError("bad"))],
        name="test",
    )
    out = await multi.search({})
    assert out == []
    assert set(multi.last_errors.keys()) == {"a", "b", "c"}
    assert "RuntimeError" in multi.last_errors["a"]
    assert "ValueError" in multi.last_errors["c"]


@pytest.mark.asyncio
async def test_integration_with_real_mock_backends():
    """Sanity check : MultiSourceBackend wrappe bien des MockBackend reels."""
    multi = MultiSourceBackend([
        MockBackend("linkedin"),
        MockBackend("indeed"),
    ])
    out = await multi.search({"keywords": "data", "max_results": 5})
    # linkedin reussit (MockBackend genere toujours des resultats), donc on prend linkedin
    assert len(out) == 5
    assert all(o.source == "linkedin" for o in out)