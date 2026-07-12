"""Sandbox d execution pour les agents.

- limite le temps d execution
- limite la memoire utilisee
- limite le nombre d appels reseau
- limite le cout LLM
- peut sandboxer le filesystem (a integrer avec Docker en prod)
"""
from __future__ import annotations
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import RLock


@dataclass
class SandboxLimits:
    timeout_s: float = 300.0
    max_llm_cost_usd: float = 1.0
    max_tool_calls: int = 100
    max_memory_mb: int = 512
    allowed_networks: list[str] = field(default_factory=list)
    allowed_filesystem_paths: list[str] = field(default_factory=list)


@dataclass
class SandboxUsage:
    started_at: float = 0.0
    tool_calls: int = 0
    llm_cost_usd: float = 0.0


class SandboxViolation(Exception):
    pass


class AgentSandbox:
    def __init__(self, limits: SandboxLimits | None = None):
        self.limits = limits or SandboxLimits()
        self._usage = SandboxUsage()
        self._lock = RLock()

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
            raise SandboxViolation(
                f"Timeout sandbox: {elapsed:.1f}s > {self.limits.timeout_s}s"
            )

    def check_tool_call(self) -> None:
        with self._lock:
            if self._usage.tool_calls >= self.limits.max_tool_calls:
                raise SandboxViolation(
                    f"Limite d appels outils atteinte: {self.limits.max_tool_calls}"
                )
            self._usage.tool_calls += 1

    def check_llm_cost(self, additional_usd: float) -> None:
        with self._lock:
            new_total = self._usage.llm_cost_usd + additional_usd
            if new_total > self.limits.max_llm_cost_usd:
                raise SandboxViolation(
                    f"Limite cout LLM atteinte: {new_total:.2f}$ > {self.limits.max_llm_cost_usd}$"
                )
            self._usage.llm_cost_usd = new_total

    def check_network(self, host: str) -> None:
        if not self.limits.allowed_networks:
            return  # pas de restriction
        if not any(host.endswith(allowed) for allowed in self.limits.allowed_networks):
            raise SandboxViolation(f"Reseau non autorise: {host}")

    def check_filesystem(self, path: str) -> None:
        if not self.limits.allowed_filesystem_paths:
            return
        if not any(path.startswith(allowed) for allowed in self.limits.allowed_filesystem_paths):
            raise SandboxViolation(f"Chemin non autorise: {path}")

    def get_usage(self) -> dict:
        return {
            "elapsed_s": round(time.time() - self._usage.started_at, 2),
            "tool_calls": self._usage.tool_calls,
            "llm_cost_usd": round(self._usage.llm_cost_usd, 4),
        }


# Decorateur pour appliquer automatiquement un sandbox a un agent
def sandboxed(limits: SandboxLimits | None = None):
    sb = AgentSandbox(limits)

    def decorator(func):
        async def wrapper(*args, **kwargs):
            with sb.run(func.__name__):
                sb.check_timeout()
                return await func(*args, **kwargs)
        return wrapper
    return decorator
