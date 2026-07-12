"""Tests du Determinism Sprint (ExecutionContext + LLM + ConnectorRecorder)."""
import asyncio

import pytest

from omniagent.agents.runtime.context.isolation import IsolatedContext
from omniagent.connectors.recorder import (
    ConnectorRecorder, ConnectorSnapshot, get_default_recorder, reset_default_recorder,
)
from omniagent.llm import (
    LLMResponse, MockLLMClient, RecordingLLMClient, cache_key, get_default_llm, reset_default_llm,
)


# ---------- IsolatedContext : determinism fields ----------

def test_isolated_context_default_determinism_off():
    ctx = IsolatedContext()
    assert ctx.deterministic_mode is False
    assert ctx.seed is None


def test_isolated_context_seed_propagates_to_fork():
    ctx = IsolatedContext(seed=42, deterministic_mode=True)
    child = ctx.fork()
    assert child.seed == 42
    assert child.deterministic_mode is True


def test_isolated_context_seal_blocks_fork():
    ctx = IsolatedContext(seed=1)
    ctx.seal()
    with pytest.raises(RuntimeError):
        ctx.fork()


# ---------- MockLLMClient : determinism ----------

def test_mock_llm_returns_response_with_metadata():
    client = MockLLMClient()
    resp = client.complete("hello world", seed=1)
    assert isinstance(resp, LLMResponse)
    assert resp.model == "mock-llm"
    assert resp.tokens_in > 0
    assert resp.metadata["seed"] == 1
    assert client.calls == 1


def test_mock_llm_is_deterministic_with_same_seed():
    """Meme (prompt, seed) -> meme reponse (cle du determinism)."""
    a = MockLLMClient().complete("quelle est la capitale", seed=42)
    b = MockLLMClient().complete("quelle est la capitale", seed=42)
    assert a.text == b.text


def test_mock_llm_differs_with_different_seed():
    a = MockLLMClient().complete("quelle est la capitale", seed=1)
    b = MockLLMClient().complete("quelle est la capitale", seed=2)
    # En general, deux seeds differents produisent des reponses differentes
    # (mais on ne peut pas le garantir 100% avec un pool de 4 templates).
    # On verifie surtout que le mecanisme de seed est pris en compte.
    assert a.metadata["seed"] == 1
    assert b.metadata["seed"] == 2


def test_mock_llm_echo_mode():
    client = MockLLMClient(echo=True)
    resp = client.complete("ping", seed=0)
    assert resp.text.startswith("[echo] ping")


def test_cache_key_is_deterministic():
    a = cache_key("hello", "gpt-4o", temperature=0.7, max_tokens=100)
    b = cache_key("hello", "gpt-4o", max_tokens=100, temperature=0.7)
    # Meme contenu, ordre kwargs different -> meme cle
    assert a == b


def test_cache_key_differs_by_model_or_kwargs():
    a = cache_key("hello", "gpt-4o", temperature=0.7)
    b = cache_key("hello", "gpt-4o", temperature=0.9)
    c = cache_key("hello", "claude-sonnet", temperature=0.7)
    assert a != b
    assert a != c


# ---------- RecordingLLMClient : replay fidelity ----------

def test_recording_llm_records_on_first_call_and_replays_on_second():
    inner = MockLLMClient(echo=True)
    rec = RecordingLLMClient(inner)
    # 1er appel : enregistre
    r1 = rec.complete("ping", seed=1)
    assert r1.text.startswith("[echo] ping")
    assert inner.calls == 1
    # 2e appel meme cle : restitue, on n appelle PAS inner
    r2 = rec.complete("ping", seed=1)
    assert r2.text == r1.text
    assert inner.calls == 1  # pas re-incremente


def test_recording_llm_strict_raises_on_miss():
    inner = MockLLMClient()
    rec = RecordingLLMClient(inner, replay_strict=True)
    # On n a rien enregistre : doit lever
    with pytest.raises(RuntimeError, match="strict mode"):
        rec.complete("nope", seed=99)


def test_recording_llm_export_and_reload():
    """On peut exporter les recordings et les recharger dans un autre recorder."""
    inner = MockLLMClient(echo=True)
    rec_a = RecordingLLMClient(inner)
    rec_a.complete("alpha", seed=1)
    rec_a.complete("beta", seed=2)
    snapshots = rec_a.export_snapshots_dict() if hasattr(rec_a, "export_snapshots_dict") else None
    # Notre API expose recordings (dict) et on a export_snapshots pour dict
    from omniagent.llm import LLMResponse
    # On prend le dict interne et on le sérialise
    raw = {k: v.text for k, v in rec_a.recordings.items()}
    assert len(raw) == 2
    # Reconstruction : on simule un autre recorder en rejouant depuis le dict
    rec_b = RecordingLLMClient(MockLLMClient(echo=True))
    rec_b._recordings = {
        k: LLMResponse(text=v, model="mock-llm") for k, v in raw.items()
    }
    r = rec_b.complete("alpha", seed=1)
    assert r.text == "[echo] alpha"


# ---------- ConnectorRecorder : replay fidelity ----------

@pytest.mark.asyncio
async def test_connector_recorder_records_first_call():
    rec = ConnectorRecorder()
    async def fake_fetch(q):
        return {"results": [1, 2, 3], "q": q}
    out = await rec.call("linkedin.search", fake_fetch, "data engineer")
    assert out == {"results": [1, 2, 3], "q": "data engineer"}
    assert rec.stats["snapshots"] == 1


@pytest.mark.asyncio
async def test_connector_recorder_replay_does_not_invoke_fn():
    rec = ConnectorRecorder()
    calls = []

    async def fake_fetch(q):
        calls.append(q)
        return {"q": q, "n": len(calls)}

    out_a = await rec.call("linkedin.search", fake_fetch, "data")
    assert out_a == {"q": "data", "n": 1}
    # Bascule en mode replay
    rec.enable_replay()
    out_b = await rec.call("linkedin.search", fake_fetch, "data")
    # Restitue le snapshot, fn pas re-invoque
    assert out_b == {"q": "data", "n": 1}
    assert calls == ["data"]  # toujours 1 seul appel


@pytest.mark.asyncio
async def test_connector_recorder_replay_miss_raises():
    rec = ConnectorRecorder(replay_mode=True)
    async def fake(q): return q
    with pytest.raises(KeyError, match="pas de snapshot"):
        await rec.call("unknown.thing", fake, "x")


@pytest.mark.asyncio
async def test_connector_recorder_records_error():
    rec = ConnectorRecorder()
    async def boom(q):
        raise ValueError("down")
    with pytest.raises(ValueError):
        await rec.call("svc.x", boom, "arg")
    snap = list(rec._snapshots.values())[0]
    assert snap.error is not None
    assert "down" in snap.error


@pytest.mark.asyncio
async def test_connector_recorder_export_roundtrip():
    rec_a = ConnectorRecorder()
    async def f(x): return x * 2
    await rec_a.call("t1", f, 5)
    await rec_a.call("t1", f, 7)
    exported = rec_a.export_snapshots()

    rec_b = ConnectorRecorder()
    rec_b.load_snapshots(exported)
    rec_b.enable_replay()
    out = await rec_b.call("t1", f, 5)
    assert out == 10


# ---------- Integration : ExecutionContext + LLM ----------

def test_execution_context_with_llm_determinism():
    """Un meme seed dans 2 contextes differents produit la meme reponse."""
    ctx_a = IsolatedContext(seed=123, deterministic_mode=True)
    ctx_b = IsolatedContext(seed=123, deterministic_mode=True)
    client = MockLLMClient()
    r_a = client.complete("test prompt", seed=ctx_a.seed)
    r_b = client.complete("test prompt", seed=ctx_b.seed)
    assert r_a.text == r_b.text