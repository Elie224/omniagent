"""Tests du Policy Engine."""
import pytest
from datetime import datetime
from omniagent.core.policy.engine import (
    PolicyEngine, PolicyContext, PolicyDecision, PolicyResult, get_default_engine,
)


def test_default_engine_allows_safe_context():
    ctx = PolicyContext(
        user_id="u1", user_role="user", agent_name="agent_x",
        module="emploi", country="FR", plan="free", balance_usd=10.0,
    )
    r = get_default_engine().evaluate(ctx)
    assert r.decision == PolicyDecision.ALLOW


def test_country_sanctioned_denied():
    ctx = PolicyContext(
        user_id="u1", user_role="user", agent_name="agent_x",
        module="emploi", country="IR", plan="pro", balance_usd=10.0,
    )
    r = get_default_engine().evaluate(ctx)
    assert r.decision == PolicyDecision.DENY
    assert r.rule == "country_sanctioned"


def test_balance_negative_denied():
    ctx = PolicyContext(
        user_id="u1", user_role="user", agent_name="agent_x",
        module="emploi", country="FR", plan="pro", balance_usd=-5.0,
    )
    r = get_default_engine().evaluate(ctx)
    assert r.decision == PolicyDecision.DENY
    assert r.rule == "balance_must_be_positive"


def test_business_hours_denied_at_3am():
    ctx = PolicyContext(
        user_id="u1", user_role="user", agent_name="agent_communication",
        module="recouvrement", country="FR", plan="pro", balance_usd=10.0,
        timestamp=datetime(2026, 7, 4, 3, 0, 0),
    )
    r = get_default_engine().evaluate(ctx)
    assert r.decision == PolicyDecision.DENY
    assert r.rule == "business_hours"


def test_high_value_requires_approval():
    ctx = PolicyContext(
        user_id="u1", user_role="user", agent_name="agent_vocal",
        module="recouvrement", country="FR", plan="pro", balance_usd=10.0,
        metadata={"amount_eur": 50000},
    )
    r = get_default_engine().evaluate(ctx)
    assert r.decision == PolicyDecision.REQUIRE_APPROVAL
    assert r.requires_approval_from == "finance_lead"


def test_deny_rule_wins_over_allow_rule():
    eng = PolicyEngine()

    def always_deny(ctx):
        return PolicyResult(PolicyDecision.DENY, "test", "test")

    eng.register("deny", always_deny, priority=10)  # haute priorite
    ctx = PolicyContext(user_id="u", user_role="u", agent_name="a",
                         module="emploi", country="FR", plan="free")
    r = eng.evaluate(ctx)
    assert r.decision == PolicyDecision.DENY


def test_rule_error_does_not_break_pipeline():
    eng = PolicyEngine()

    def broken(ctx):
        raise RuntimeError("oops")

    def fallback(ctx):
        return PolicyResult(PolicyDecision.ALLOW, "fallback", "ok")

    eng.register("broken", broken, priority=10)
    eng.register("fallback", fallback, priority=20)
    ctx = PolicyContext(user_id="u", user_role="u", agent_name="a",
                         module="emploi", country="FR", plan="free")
    r = eng.evaluate(ctx)
    assert r.decision == PolicyDecision.ALLOW