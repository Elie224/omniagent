"""TenantContext : contexte de l organisation courante.

Chaque requete, agent ou tache tourne dans un TenantContext isole.
Les memoires, quotas, et policies sont scopes par tenant.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from typing import Any
from uuid import uuid4


class TenantPlan(str, Enum):
    FREE = "free"
    SOLO = "solo"
    PRO = "pro"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


class TenantStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"
    CHURNED = "churned"


@dataclass
class Tenant:
    tenant_id: str
    name: str
    plan: TenantPlan
    status: TenantStatus = TenantStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = field(default_factory=dict)
    quotas: dict = field(default_factory=dict)


# Quotas par plan
PLAN_QUOTAS: dict[TenantPlan, dict] = {
    TenantPlan.FREE:       {"agents_per_month": 50,    "llm_cost_usd": 0.50,  "users": 1},
    TenantPlan.SOLO:       {"agents_per_month": 500,   "llm_cost_usd": 5.00,  "users": 1},
    TenantPlan.PRO:        {"agents_per_month": 5000,  "llm_cost_usd": 30.00, "users": 5},
    TenantPlan.BUSINESS:   {"agents_per_month": 25000, "llm_cost_usd": 100.0, "users": 25},
    TenantPlan.ENTERPRISE: {"agents_per_month": -1,    "llm_cost_usd": -1.0,  "users": -1},  # -1 = illimite
}


@dataclass
class TenantContext:
    """Contexte thread/task-local : qui est-ce qui tourne, pour quel tenant."""
    tenant_id: str
    user_id: str
    request_id: str = field(default_factory=lambda: str(uuid4()))
    plan: TenantPlan = TenantPlan.FREE
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id, "user_id": self.user_id,
            "request_id": self.request_id, "plan": self.plan.value,
        }


class TenantRegistry:
    """Registre des tenants + leurs quotas."""

    def __init__(self):
        self._tenants: dict[str, Tenant] = {}
        self._lock = RLock()
        self._usage: dict[str, dict] = {}  # tenant_id -> {agents, cost}

    def create(self, name: str, plan: TenantPlan, tenant_id: str | None = None) -> Tenant:
        tid = tenant_id or str(uuid4())
        with self._lock:
            t = Tenant(tenant_id=tid, name=name, plan=plan,
                        quotas=PLAN_QUOTAS[plan].copy())
            self._tenants[tid] = t
        return t

    def get(self, tenant_id: str) -> Tenant | None:
        return self._tenants.get(tenant_id)

    def suspend(self, tenant_id: str) -> None:
        t = self._tenants.get(tenant_id)
        if t:
            t.status = TenantStatus.SUSPENDED

    def record_usage(self, tenant_id: str, agents: int = 0, cost: float = 0.0) -> None:
        with self._lock:
            u = self._usage.setdefault(tenant_id, {"agents": 0, "cost": 0.0})
            u["agents"] += agents
            u["cost"] += cost

    def check_quota(self, tenant_id: str, requested_agents: int = 1,
                     requested_cost: float = 0.0) -> tuple[bool, str]:
        t = self.get(tenant_id)
        if not t:
            return False, f"Tenant inconnu: {tenant_id}"
        if t.status != TenantStatus.ACTIVE:
            return False, f"Tenant {t.status.value}"
        usage = self._usage.get(tenant_id, {"agents": 0, "cost": 0.0})
        max_agents = t.quotas.get("agents_per_month", -1)
        max_cost = t.quotas.get("llm_cost_usd", -1)
        if max_agents != -1 and usage["agents"] + requested_agents > max_agents:
            return False, f"Quota agents atteint: {usage['agents']}/{max_agents}"
        if max_cost != -1 and usage["cost"] + requested_cost > max_cost:
            return False, f"Quota cout atteint: {usage['cost']:.2f}/{max_cost:.2f} USD"
        return True, "OK"

    def get_usage(self, tenant_id: str) -> dict:
        return dict(self._usage.get(tenant_id, {"agents": 0, "cost": 0.0}))


tenant_registry = TenantRegistry()


class TenantContextManager:
    """Context manager thread/task-local pour propager le TenantContext."""

    _local_stack: list[TenantContext] = []

    def __init__(self, ctx: TenantContext):
        self._ctx = ctx

    def __enter__(self) -> TenantContext:
        TenantContextManager._local_stack.append(self._ctx)
        return self._ctx

    def __exit__(self, *exc) -> None:
        TenantContextManager._local_stack.pop()

    @classmethod
    def current(cls) -> TenantContext | None:
        return cls._local_stack[-1] if cls._local_stack else None
