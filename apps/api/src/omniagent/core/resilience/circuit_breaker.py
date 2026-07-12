"""Circuit Breaker : protection des appels externes (Twilio, Pennylane, Hunter...).

3 etats :
- CLOSED    : appels normaux. Si trop d echecs consecutifs -> OPEN
- OPEN      : appels refuses immediatement. Apres un delai -> HALF_OPEN
- HALF_OPEN : 1 appel test autorise. Si succes -> CLOSED, sinon -> OPEN

Concurrence : on utilise un Lock pour serialiser les changements d etat
(un seul test a la fois en HALF_OPEN).
"""
from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Leve quand on tente un appel alors que le circuit est ouvert."""


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5         # echecs consecutifs avant ouverture
    success_threshold: int = 2         # succes consecutifs en HALF_OPEN avant fermeture
    reset_timeout_s: float = 30.0      # temps en OPEN avant de tester
    half_open_max_calls: int = 1       # nb d appels tests simultanes


@dataclass
class CircuitStats:
    state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    opened_at: float | None = None
    total_calls: int = 0
    total_failures: int = 0
    total_rejected: int = 0
    last_failure_at: float | None = None
    last_state_change_at: float = field(default_factory=time.time)


class CircuitBreaker:
    def __init__(self, name: str, config: CircuitBreakerConfig | None = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.stats = CircuitStats()
        self._lock = asyncio.Lock()

    def _now(self) -> float:
        return time.time()

    async def _transition(self, new_state: CircuitState) -> None:
        if self.stats.state == new_state:
            return
        self.stats.state = new_state
        self.stats.last_state_change_at = self._now()
        if new_state == CircuitState.OPEN:
            self.stats.opened_at = self._now()
        if new_state == CircuitState.CLOSED:
            self.stats.consecutive_failures = 0
            self.stats.consecutive_successes = 0
            self.stats.opened_at = None

    async def _maybe_half_open(self) -> None:
        if self.stats.state == CircuitState.OPEN and self.stats.opened_at is not None:
            if (self._now() - self.stats.opened_at) >= self.config.reset_timeout_s:
                await self._transition(CircuitState.HALF_OPEN)
                self.stats.consecutive_successes = 0

    async def call(self, fn: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        """Execute fn() en respectant le circuit. Leve CircuitOpenError si ouvert."""
        async with self._lock:
            await self._maybe_half_open()
            if self.stats.state == CircuitState.OPEN:
                self.stats.total_rejected += 1
                raise CircuitOpenError(
                    f"Circuit {self.name!r} est ouvert "
                    f"(reset dans {self.config.reset_timeout_s}s)"
                )
            self.stats.total_calls += 1

        try:
            result = await fn(*args, **kwargs)
        except Exception:
            await self._on_failure()
            raise
        else:
            await self._on_success()
            return result

    async def _on_success(self) -> None:
        async with self._lock:
            self.stats.consecutive_failures = 0
            self.stats.consecutive_successes += 1
            if (self.stats.state == CircuitState.HALF_OPEN
                    and self.stats.consecutive_successes >= self.config.success_threshold):
                await self._transition(CircuitState.CLOSED)

    async def _on_failure(self) -> None:
        async with self._lock:
            self.stats.consecutive_failures += 1
            self.stats.total_failures += 1
            self.stats.last_failure_at = self._now()
            if (self.stats.state in {CircuitState.CLOSED, CircuitState.HALF_OPEN}
                    and self.stats.consecutive_failures >= self.config.failure_threshold):
                await self._transition(CircuitState.OPEN)

    def snapshot(self) -> dict:
        return {
            "name": self.name,
            "state": self.stats.state.value,
            "consecutive_failures": self.stats.consecutive_failures,
            "consecutive_successes": self.stats.consecutive_successes,
            "total_calls": self.stats.total_calls,
            "total_failures": self.stats.total_failures,
            "total_rejected": self.stats.total_rejected,
            "opened_at": self.stats.opened_at,
        }


class CircuitBreakerRegistry:
    """Registre des circuit breakers (un par connecteur)."""

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}

    def get(self, name: str, config: CircuitBreakerConfig | None = None) -> CircuitBreaker:
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]

    def all(self) -> list[CircuitBreaker]:
        return list(self._breakers.values())

    def reset(self, name: str) -> None:
        if name in self._breakers:
            self._breakers[name] = CircuitBreaker(name, self._breakers[name].config)


circuit_breaker_registry = CircuitBreakerRegistry()
