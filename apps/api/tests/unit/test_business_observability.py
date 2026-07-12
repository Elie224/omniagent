"""Tests de l observabilite metier."""
import pytest


def test_record_run_and_score():
    from omniagent.core.observability.business.scoring import business_observability
    business_observability.reset()
    for _ in range(8):
        business_observability.record_run("agent_x", success=True, duration_ms=100,
                                          cost_usd=0.01, business_value=50)
    for _ in range(2):
        business_observability.record_run("agent_x", success=False, duration_ms=200,
                                          cost_usd=0.01)
    score = business_observability.get_score("agent_x")
    assert score["runs"] == 10
    assert score["success_rate"] == 0.8
    assert score["business_value"] == 400


def test_anomaly_detection():
    from omniagent.core.observability.business.scoring import business_observability
    business_observability.reset()
    for _ in range(10):
        business_observability.record_run("agent_bad", success=False, duration_ms=100)
    anomalies = business_observability.detect_anomalies()
    assert "agent_bad" in anomalies
    assert "high_failure_rate" in anomalies["agent_bad"]


def test_dashboard():
    from omniagent.core.observability.business.scoring import business_observability
    business_observability.reset()
    business_observability.record_run("agent_a", True, 100, 0.01, 10)
    business_observability.record_run("agent_b", False, 200, 0.02)
    d = business_observability.dashboard()
    assert d["totals"]["runs"] == 2
    assert d["totals"]["business_value"] == 10
    assert len(d["agents"]) == 2