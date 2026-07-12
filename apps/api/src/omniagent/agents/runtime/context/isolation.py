"""Context isolation : chaque agent recoit un contexte totalement isole.

Le contexte contient : tenant, user, request, memory scope, secrets limites.
Apres l execution, le contexte est detruit.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class IsolatedContext:
    """Contexte complet d une execution d agent."""
    context_id: str = field(default_factory=lambda: str(uuid4()))
    tenant_id: str = "default"
    user_id: str = "anonymous"
    request_id: str = field(default_factory=lambda: str(uuid4()))
    agent_name: str = ""
    input: dict = field(default_factory=dict)
    memory_keys: set[str] = field(default_factory=set)
    secrets: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    _sealed: bool = False

    # --- Determinism (Sprint 3+ : ExecutionContext / replay fidelity) ---
    # Si `deterministic_mode=True`, les sub-agents et connecteurs DOIVENT
    # utiliser un seed deterministe pour leurs generations aleatoires.
    # Par defaut False (comportement actuel : pas de contrainte).
    deterministic_mode: bool = False
    # Seed : si None, derive de (context_id, request_id) pour reproductibilite
    # intra-contexte sans casser les autres.
    seed: int | None = None

    def seal(self) -> None:
        """Ferme le contexte : plus aucune modification possible."""
        self._sealed = True

    def fork(self) -> "IsolatedContext":
        """Cree un fork pour execution parallele (independance totale)."""
        if self._sealed:
            raise RuntimeError("Impossible de forker un contexte scelle")
        return IsolatedContext(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            agent_name=self.agent_name,
            input=deepcopy(self.input),
            memory_keys=set(self.memory_keys),
            secrets=deepcopy(self.secrets),
            metadata=deepcopy(self.metadata),
            deterministic_mode=self.deterministic_mode,
            seed=self.seed,
        )

    def grant_secret(self, key: str, value: Any, ttl_s: int = 600) -> None:
        if self._sealed:
            raise RuntimeError("Contexte scelle")
        self.secrets[key] = {"value": value, "ttl_s": ttl_s, "expires_at": ttl_s}

    def get_secret(self, key: str) -> Any | None:
        s = self.secrets.get(key)
        if s is None:
            return None
        return s["value"]

    def __repr__(self) -> str:
        return f"IsolatedContext(id={self.context_id}, agent={self.agent_name}, user={self.user_id})"


class ContextPool:
    """Pool de contextes avec limite (anti-abus)."""

    def __init__(self, max_active: int = 100):
        self._active: dict[str, IsolatedContext] = {}
        self._max = max_active

    def acquire(self, **kwargs) -> IsolatedContext:
        if len(self._active) >= self._max:
            raise RuntimeError(f"Pool sature: {self._max} contextes actifs")
        ctx = IsolatedContext(**kwargs)
        self._active[ctx.context_id] = ctx
        return ctx

    def release(self, context_id: str) -> None:
        self._active.pop(context_id, None)

    def stats(self) -> dict:
        return {"active": len(self._active), "max": self._max}


context_pool = ContextPool()