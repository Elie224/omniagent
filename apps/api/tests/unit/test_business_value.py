"""Tests des heuristiques business_value par module."""
from omniagent.core.observability.business import value


def test_emploi_extracts_applications_sent():
    out = {"applications_sent": 3, "other": "ignored"}
    assert value.compute_business_value("agent_emploi_sub", out) == 3.0  # via prefixe agent_emploi_
    assert value.compute_business_value("agent_linkedin", out) == 3.0
    assert value.compute_business_value("agent_cv", out) == 3.0
    assert value.compute_business_value("agent_lettre", out) == 3.0


def test_marketing_extracts_posts_generated():
    out = {"posts_generated": 5}
    assert value.compute_business_value("agent_marketing_x", out) == 5.0  # via prefixe agent_marketing_
    assert value.compute_business_value("agent_instagram", out) == 5.0
    assert value.compute_business_value("agent_x", out) == 5.0
    assert value.compute_business_value("agent_tiktok", out) == 5.0


def test_recouvrement_extracts_amount_collected():
    out = {"amount_collected": 1500.5}
    assert value.compute_business_value("agent_recouvrement_x", out) == 1500.5  # via prefixe agent_recouvrement_
    assert value.compute_business_value("agent_analyse_impayes", out) == 1500.5
    assert value.compute_business_value("agent_communication", out) == 1500.5
    assert value.compute_business_value("agent_vocal", out) == 1500.5


def test_fallback_uses_generic_value_key():
    # Agent non rfrence explicitement : on tente la cle generique "value"
    out = {"value": 42}
    assert value.compute_business_value("agent_transverse_xyz", out) == 42.0


def test_non_dict_output_returns_zero():
    assert value.compute_business_value("agent_emploi", "une string") == 0.0
    assert value.compute_business_value("agent_emploi", None) == 0.0
    assert value.compute_business_value("agent_emploi", [1, 2, 3]) == 0.0


def test_missing_keys_return_zero():
    # L output est un dict mais sans la cle attendue pour ce module
    assert value.compute_business_value("agent_emploi", {"unrelated": 1}) == 0.0
    assert value.compute_business_value("agent_marketing", {}) == 0.0


def test_non_numeric_values_fall_back_to_zero():
    out = {"applications_sent": "beaucoup"}
    assert value.compute_business_value("agent_emploi", out) == 0.0