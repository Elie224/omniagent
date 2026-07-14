"""LLM abstraction layer (replay-safe).

But : isoler les appels LLM derriere une interface pour qu on puisse :
1. Tester sans payer (MockLLMClient deterministe par seed)
2. Rejouer un run exact (RecordingLLMClient : stocke input/output et les
   restitue fidelement au replay)
3. Brancher plusieurs providers (OpenAI, Anthropic, etc.) sans toucher
   aux agents

Convention : tous les LLMClient exposent `complete(prompt, **kw) -> LLMResponse`
avec seed (pour determinism) et un cache key (pour replay).
"""
from __future__ import annotations
import hashlib
import random
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class LLMResponse:
    """Reponse normalisee d un LLM."""
    text: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    metadata: dict = field(default_factory=dict)


class LLMClient(Protocol):
    """Interface minimale d un client LLM."""

    def complete(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """Genere une completion textuelle."""
        ...

    @property
    def name(self) -> str:
        """Nom du model (utilise pour le cost tracking)."""
        ...


def cache_key(prompt: str, model: str, **kwargs: Any) -> str:
    """Hash deterministe (prompt, model, kwargs) -> cle de cache.

    Utilise par RecordingLLMClient pour stocker et retrouver les outputs.
    """
    h = hashlib.sha256()
    h.update(model.encode("utf-8"))
    h.update(b"\x00")
    h.update(prompt.encode("utf-8"))
    h.update(b"\x00")
    for k in sorted(kwargs.keys()):
        h.update(k.encode("utf-8"))
        h.update(b"=")
        h.update(str(kwargs[k]).encode("utf-8"))
        h.update(b"&")
    return h.hexdigest()


class MockLLMClient:
    """LLM client deterministe (par seed) : reponse generee a partir du prompt.

    Pas d appel reseau. Pour tests, dev, et replay deterministe.
    Strategie : on derive un Random du hash(prompt + seed) pour choisir parmi
    un petit set de reponses plausibles. Reproductible a 100% tant que le
    seed est fixe.
    """

    def __init__(self, name: str = "mock-llm", echo: bool = False):
        self._name = name
        self._echo = echo
        self.calls = 0

    @property
    def name(self) -> str:
        return self._name

    def complete(self, prompt: str, **kwargs: Any) -> LLMResponse:
        seed = kwargs.get("seed")
        self.calls += 1
        if self._echo:
            text = f"[echo] {prompt[:200]}"
        else:
            key_src = prompt + "|" + (str(seed) if seed is not None else "no-seed")
            h = hashlib.sha256(key_src.encode()).digest()
            rng = random.Random(int.from_bytes(h[:8], "big"))
            templates = [
                f"Analyse de : {prompt[:80]}...",
                f"Reponse generee pour le prompt (len={len(prompt)}).",
                f"Resultat : OK. Le prompt contient {len(prompt.split())} mots.",
                f"Hypothese : la requete vise a {prompt.split()[0] if prompt.split() else '?'}.",
            ]
            text = rng.choice(templates)
        return LLMResponse(
            text=text,
            model=self._name,
            tokens_in=len(prompt.split()),
            tokens_out=len(text.split()),
            cost_usd=0.0,
            metadata={"seed": seed, "echo": self._echo},
        )


class RecordingLLMClient:
    """LLM client qui snapshot les outputs pour replay exact.

    Wrap n importe quel LLMClient. A chaque appel, on stocke (cache_key ->
    LLMResponse) dans `recordings`. En replay, on restitue le snapshot
    sans appeler le vrai LLM.

    Si pas d enregistrement pour une cle et qu on est en `replay_strict=True`,
    on leve une erreur (anti-drift). Sinon on delegue au client sous-jacent.
    """

    def __init__(self, inner: LLMClient, replay_strict: bool = False):
        self._inner = inner
        self._recordings: dict[str, LLMResponse] = {}
        self._replay_strict = replay_strict

    @property
    def name(self) -> str:
        return self._inner.name

    @property
    def recordings(self) -> dict[str, LLMResponse]:
        return dict(self._recordings)

    def complete(self, prompt: str, **kwargs: Any) -> LLMResponse:
        model = self._inner.name
        key = cache_key(prompt, model, **kwargs)
        if key in self._recordings:
            return self._recordings[key]
        if self._replay_strict:
            raise RuntimeError(
                f"RecordingLLMClient en strict mode : pas d enregistrement "
                f"pour la cle {key[:16]}... (prompt={prompt[:60]!r})"
            )
        resp = self._inner.complete(prompt, **kwargs)
        self._recordings[key] = resp
        return resp


_default_client: LLMClient | None = None


def get_default_llm() -> LLMClient:
    """Retourne le LLM client par defaut (singleton).

    Strategie : si une cle Anthropic est dispo, on retourne un wrapper stub ;
    sinon si une cle OpenAI est dispo, on retourne un wrapper stub ; sinon
    un MockLLMClient deterministe. Permet de dev sans cle API tout en
    gardant l interface stable.
    """
    global _default_client
    if _default_client is not None:
        return _default_client
    from omniagent.core.config import settings
    if settings.anthropic_api_key:
        _default_client = MockLLMClient(name="anthropic-stub")
    elif settings.openai_api_key:
        _default_client = MockLLMClient(name="openai-stub")
    else:
        _default_client = MockLLMClient(name="mock-llm")
    return _default_client


def reset_default_llm() -> None:
    """Reinitialise le singleton (utile pour les tests)."""
    global _default_client
    _default_client = None