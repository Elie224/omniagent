"""Tests du multi-tenant."""
import pytest
from omniagent.tenancy.context import (
    tenant_registry, TenantPlan, TenantContext, TenantContextManager,
)


def setup_function(function):
    """Reset le registre entre chaque test."""
    tenant_registry._tenants.clear()
    tenant_registry._usage.clear()


def test_create_tenant():
    t = tenant_registry.create("Acme", TenantPlan.PRO, tenant_id="acme")
    assert t.name == "Acme"
    assert t.plan == TenantPlan.PRO
    assert tenant_registry.get("acme") is not None


def test_quota_within_limits():
    tenant_registry.create("Acme", TenantPlan.SOLO, tenant_id="acme2")
    ok, msg = tenant_registry.check_quota("acme2", requested_agents=10, requested_cost=0.5)
    assert ok is True


def test_quota_exceeded_agents():
    tenant_registry.create("Acme", TenantPlan.FREE, tenant_id="acme3")
    for _ in range(50):
        tenant_registry.record_usage("acme3", agents=1)
    ok, msg = tenant_registry.check_quota("acme3", requested_agents=1)
    assert ok is False
    assert "agents" in msg.lower()


def test_quota_exceeded_cost():
    tenant_registry.create("Acme", TenantPlan.FREE, tenant_id="acme4")
    tenant_registry.record_usage("acme4", cost=0.6)
    ok, msg = tenant_registry.check_quota("acme4", requested_cost=0.1)
    assert ok is False
    assert "cout" in msg.lower()


def test_enterprise_has_unlimited_quotas():
    tenant_registry.create("Big", TenantPlan.ENTERPRISE, tenant_id="big")
    for _ in range(100):
        tenant_registry.record_usage("big", agents=100, cost=100)
    ok, _ = tenant_registry.check_quota("big", requested_agents=1000, requested_cost=1000)
    assert ok is True


def test_tenant_context_manager():
    ctx = TenantContext(tenant_id="t", user_id="u")
    with TenantContextManager(ctx) as c:
        assert TenantContextManager.current() is c
    assert TenantContextManager.current() is None


def test_suspend_tenant_denies():
    tenant_registry.create("Acme", TenantPlan.PRO, tenant_id="susp")
    tenant_registry.suspend("susp")
    ok, msg = tenant_registry.check_quota("susp")
    assert ok is False
    assert "suspended" in msg.lower()