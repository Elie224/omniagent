"""Connector Manager : instancie, gere le cycle de vie, fait respecter les quotas par connecteur.

Couches de protection par appel (via `call()` ou `use()`) :
  1. Semaphore de concurrence (`max_concurrent`)
  2. Circuit Breaker (etat ferme / ouvert / half-open) -> refuse les appels si Open
  3. Compteurs metriques par connecteur
"""
from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Awaitable, Callable

from omniagent.core.registry.connector_registry import (
    ConnectorRegistry, ConnectorSpec, connector_registry
)
from omniagent.core.observability.metrics import metrics
from omniagent.core.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitOpenError,
    circuit_breaker_registry,
)


# Config par defaut pour les connecteurs externes.
DEFAULT_CONNECTOR_BREAKER_CONFIG = CircuitBreakerConfig(
    failure_threshold=5,       # 5 echecs consecutifs -> ouvre
    success_threshold=2,       # 2 succes en half-open -> ferme
    reset_timeout_s=30.0,      # 30s avant de re-tester
)


class ConnectorManager:
    """Singleton qui gere tous les connecteurs tiers."""

    def __init__(self,
                 registry: ConnectorRegistry = connector_registry,
                 breaker_registry: CircuitBreakerRegistry = circuit_breaker_registry,
                 breaker_config: CircuitBreakerConfig | None = None):
        self._registry = registry
        self._breakers = breaker_registry
        self._breaker_config = breaker_config or DEFAULT_CONNECTOR_BREAKER_CONFIG
        self._instances: dict[str, Any] = {}
        self._locks: dict[str, asyncio.Semaphore] = {}

    def register(self, spec: ConnectorSpec) -> None:
        self._registry.register(spec)
        # Pre-creer le circuit breaker pour ce connecteur
        self._breakers.get(spec.name, self._breaker_config)

    def get(self, name: str) -> Any:
        if name not in self._instances:
            spec = self._registry.get(name)
            self._instances[name] = spec.factory()
        return self._instances[name]

    def breaker(self, name: str) -> CircuitBreaker:
        return self._breakers.get(name, self._breaker_config)

    async def call(self, name: str, fn: Callable[..., Awaitable[Any]],
                    *args, **kwargs) -> Any:
        """Appelle fn(*args, **kwargs) sur le connecteur via le circuit breaker.

        - Concurrence limitee par semaphore
        - Echecs remontent apres passage par le breaker
        - CircuitOpenError levee sans appeler fn si breaker ouvert
        """
        async with self.use(name) as _conn:
            breaker = self.breaker(name)
            return await breaker.call(fn, *args, **kwargs)

    @asynccontextmanager
    async def use(self, name: str, max_concurrent: int = 5) -> AsyncIterator[Any]:
        """Acquire un connecteur. Les erreurs sont comptabilisees par le breaker."""
        if name not in self._locks:
            self._locks[name] = asyncio.Semaphore(max_concurrent)
        async with self._locks[name]:
            metrics.counter(f"connector.{name}.calls").inc()
            try:
                yield self.get(name)
            except CircuitOpenError as e:
                metrics.counter(f"connector.{name}.rejected").inc()
                raise
            except Exception:
                metrics.counter(f"connector.{name}.errors").inc()
                # On ne NOTIFIE pas le breaker ici : c est la responsabilite de
                # `call()` qui wrap la vraie fonction. Sinon, on ouvrirait le
                # circuit sur n importe quelle exception meme non-metier.
                raise

    async def health_all(self) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for spec in self._registry.all() if hasattr(self._registry, "all") else []:
            try:
                conn = self.get(spec.name)
                results[spec.name] = await conn.health_check()
            except Exception:
                results[spec.name] = False
        return results

    def circuit_states(self) -> dict[str, dict]:
        """Retourne le snapshot de tous les breakers (utile pour /metrics)."""
        return {b.name: b.snapshot() for b in self._breakers.all()}

    async def close_all(self) -> None:
        for inst in self._instances.values():
            try:
                await inst.close()
            except Exception:
                pass
        self._instances.clear()


connector_manager = ConnectorManager()
