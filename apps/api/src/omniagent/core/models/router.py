"""Routeur de modeles LLM : choisit le bon modele selon tache + budget.

- Selection du modele (TaskType -> provider + nom)
- Appels reels OpenAI / Anthropic (lazy : si la cle API est absente, leve une erreur explicite)
- Suivi des couts et quotas par utilisateur
- Cache memoire des reponses (cle = hash(prompt + config))
"""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Any


class ModelProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class TaskType(str, Enum):
    REASONING = "reasoning"
    WRITING = "writing"
    CLASSIFICATION = "classification"
    EXTRACTION = "extraction"


@dataclass
class ModelConfig:
    provider: ModelProvider
    name: str
    cost_per_1k_input: float
    cost_per_1k_output: float
    max_tokens: int = 4096


CATALOG = {
    TaskType.REASONING: ModelConfig(ModelProvider.OPENAI, "gpt-4o", 0.005, 0.015),
    TaskType.WRITING: ModelConfig(ModelProvider.ANTHROPIC, "claude-sonnet-4-5", 0.003, 0.015),
    TaskType.CLASSIFICATION: ModelConfig(ModelProvider.OPENAI, "gpt-4o-mini", 0.00015, 0.0006),
    TaskType.EXTRACTION: ModelConfig(ModelProvider.OPENAI, "gpt-4o-mini", 0.00015, 0.0006),
}


class QuotaExceededError(Exception):
    pass


@dataclass
class LLMResponse:
    text: str
    provider: ModelProvider
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    cached: bool = False

    def to_dict(self) -> dict:
        return {
            "text": self.text, "provider": self.provider.value,
            "model": self.model, "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens, "cost_usd": round(self.cost_usd, 6),
            "cached": self.cached,
        }


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _call_provider(cfg, prompt, *, system, max_tokens, temperature):
    from omniagent.core.config import settings
    if cfg.provider == ModelProvider.OPENAI:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY manquant : appel LLM impossible")
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        r = client.chat.completions.create(
            model=cfg.name, messages=messages,
            max_tokens=max_tokens, temperature=temperature,
        )
        text = r.choices[0].message.content or ""
        in_tok = getattr(r.usage, "prompt_tokens", None) or _estimate_tokens(prompt + (system or ""))
        out_tok = getattr(r.usage, "completion_tokens", None) or _estimate_tokens(text)
        return text, in_tok, out_tok
    if cfg.provider == ModelProvider.ANTHROPIC:
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY manquant : appel LLM impossible")
        from anthropic import Anthropic
        client = Anthropic(api_key=settings.anthropic_api_key)
        r = client.messages.create(
            model=cfg.name, max_tokens=max_tokens, temperature=temperature,
            system=system or "", messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        in_tok = getattr(r.usage, "input_tokens", None) or _estimate_tokens(prompt + (system or ""))
        out_tok = getattr(r.usage, "output_tokens", None) or _estimate_tokens(text)
        return text, in_tok, out_tok
    raise ValueError(f"Provider non supporte: {cfg.provider}")


class ModelRouter:
    def __init__(self, max_cache_size: int = 256):
        self._usage = {}
        self._cache = {}
        self._cache_order = []
        self._max_cache = max_cache_size
        self._lock = Lock()

    def config_for(self, task):
        return CATALOG[task]

    def check_quota(self, user_id, max_cost_usd=5.0):
        with self._lock:
            used = self._usage.get(user_id, {}).get("cost", 0.0)
            if used >= max_cost_usd:
                raise QuotaExceededError(
                    f"Quota mensuel depasse pour {user_id}: {used:.2f}$/{max_cost_usd}$"
                )

    def record_usage(self, user_id, input_tokens, output_tokens, cfg):
        cost = (input_tokens / 1000 * cfg.cost_per_1k_input
                + output_tokens / 1000 * cfg.cost_per_1k_output)
        with self._lock:
            entry = self._usage.setdefault(user_id, {"tokens": 0, "cost": 0.0})
            entry["tokens"] += input_tokens + output_tokens
            entry["cost"] += cost
        return cost

    def get_usage(self, user_id):
        with self._lock:
            return dict(self._usage.get(user_id, {"tokens": 0, "cost": 0.0}))

    def _cache_key(self, cfg, prompt, **kwargs):
        payload = json.dumps({"m": cfg.name, "p": prompt, **kwargs}, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()

    def _cache_get(self, key):
        with self._lock:
            return self._cache.get(key)

    def _cache_put(self, key, value):
        with self._lock:
            if key in self._cache:
                return
            self._cache[key] = value
            self._cache_order.append(key)
            while len(self._cache_order) > self._max_cache:
                evict = self._cache_order.pop(0)
                self._cache.pop(evict, None)

    def generate(self, user_id, task, prompt, *, system=None, max_tokens=1024, temperature=0.2, use_cache=True):
        self.check_quota(user_id)
        cfg = self.config_for(task)
        key = self._cache_key(cfg, prompt, system=system, max_tokens=max_tokens, t=temperature)
        if use_cache:
            cached = self._cache_get(key)
            if cached is not None:
                return cached
        text, in_tok, out_tok = _call_provider(cfg, prompt, system=system,
                                                max_tokens=max_tokens, temperature=temperature)
        cost = self.record_usage(user_id, in_tok, out_tok, cfg)
        resp = LLMResponse(text=text, provider=cfg.provider, model=cfg.name,
                            input_tokens=in_tok, output_tokens=out_tok, cost_usd=cost, cached=False)
        self._cache_put(key, resp)
        return resp


model_router = ModelRouter()
