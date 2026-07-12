"""Sandbox d execution des agents (V2 : integration runtime)."""
from __future__ import annotations
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass
class SandboxLimits:
    timeout_s: float = 300.0
    max_llm_cost_usd: float = 1.0
    max_tool_calls: int = 100
    max_memory_mb: int = 512
    allowed_networks: list[str] = field(default_factory=list)
    allowed_filesystem_paths: list[str] = field(default_factory=list)
    max_context_secrets: int = 10


@dataclass
class SandboxUsage:
    started_at: float = 0.0
    tool_calls: int = 0
    llm_cost_usd: float = 0.0
    secrets_used: int = 0
    errors: list[str] = field(default_factory=list)


class SandboxViolation(Exception):
    pass


class AgentSandbox:
    def __init__(self, limits: SandboxLimits | None = None):
        self.limits = limits or SandboxLimits()
        self._usage = SandboxUsage()
        self._lock = Lock()
        self._context = None  # IsolatedContext (optionnel)

    def bind_context(self, context) -> None:
        self._context = context

    @contextmanager
    def run(self, agent_name: str):
        self._usage = SandboxUsage()
        self._usage.started_at = time.time()
        try:
            yield self
        finally:
            pass

    def check_timeout(self) -> None:
        elapsed = time.time() - self._usage.started_at
        if elapsed > self.limits.timeout_s:
            raise SandboxViolation(f"Timeout: {elapsed:.1f}s > {self.limits.timeout_s}s")

    def check_tool_call(self) -> None:
        with self._lock:
            if self._usage.tool_calls >= self.limits.max_tool_calls:
                raise SandboxViolation(f"Limite appels outils: {self.limits.max_tool_calls}")
            self._usage.tool_calls += 1

    def check_llm_cost(self, additional_usd: float) -> None:
        with self._lock:
            new_total = self._usage.llm_cost_usd + additional_usd
            if new_total > self.limits.max_llm_cost_usd:
                raise SandboxViolation(f"Limite cout LLM: {new_total:.2f}$ > {self.limits.max_llm_cost_usd}$")
            self._usage.llm_cost_usd = new_total

    def use_secret(self, key: str) -> Any | None:
        with self._lock:
            if self._usage.secrets_used >= self.limits.max_context_secrets:
                raise SandboxViolation("Trop de secrets utilises")
            self._usage.secrets_used += 1
        if self._context is None:
            return None
        return self._context.get_secret(key)

    def report_error(self, error: str) -> None:
        self._usage.errors.append(error)

    def get_usage(self) -> dict:
        return {
            "elapsed_s": round(time.time() - self._usage.started_at, 2),
            "tool_calls": self._usage.tool_calls,
            "llm_cost_usd": round(self._usage.llm_cost_usd, 4),
            "secrets_used": self._usage.secrets_used,
            "errors": self._usage.errors,
        }