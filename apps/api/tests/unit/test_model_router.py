"""Tests du routeur de modeles + quotas."""
from omniagent.core.models.router import ModelRouter, TaskType, ModelProvider, QuotaExceededError


def test_config_lookup():
    r = ModelRouter()
    assert r.config_for(TaskType.REASONING).provider == ModelProvider.OPENAI
    assert r.config_for(TaskType.WRITING).provider == ModelProvider.ANTHROPIC


def test_quota_tracking():
    r = ModelRouter()
    r.check_quota("u1", max_cost_usd=1.0)
    cfg = r.config_for(TaskType.CLASSIFICATION)
    # 2 x (1M input + 1M output) au tarif gpt-4o-mini = 2 x 0.75$ = 1.5$ > 1$
    r.record_usage("u1", 1_000_000, 1_000_000, cfg)
    r.record_usage("u1", 1_000_000, 1_000_000, cfg)
    try:
        r.check_quota("u1", max_cost_usd=1.0)
    except QuotaExceededError:
        return
    raise AssertionError("Aurait du lever QuotaExceededError")


def test_usage_per_user_isolated():
    r = ModelRouter()
    r.check_quota("u1", max_cost_usd=1.0)
    r.check_quota("u2", max_cost_usd=1.0)