"""Tests de la table de couts LLM."""
from omniagent.core.observability import costs


def test_get_cost_known_model():
    # gpt-4o : 0.005 / 1k input, 0.015 / 1k output
    # 1000 in + 500 out = 0.005 + 0.0075 = 0.0125
    c = costs.get_cost("gpt-4o", tokens_in=1000, tokens_out=500)
    assert abs(c - 0.0125) < 1e-9


def test_get_cost_unknown_model_returns_zero():
    # Pas d invention de prix pour un modele inconnu
    assert costs.get_cost("modele_qui_n_existe_pas", tokens_in=99999, tokens_out=99999) == 0.0


def test_get_cost_zero_tokens():
    assert costs.get_cost("gpt-4o", tokens_in=0, tokens_out=0) == 0.0


def test_get_cost_negative_tokens_clamped():
    # Les valeurs negatives (ne devrait pas arriver) ne doivent pas generer de cout negatif
    assert costs.get_cost("gpt-4o", tokens_in=-1000, tokens_out=300) >= 0.0


def test_register_costs_overrides():
    costs.register_costs({"mon_modele": (0.001, 0.002)})
    try:
        # 1000 in + 1000 out = 0.001 + 0.002 = 0.003
        c = costs.get_cost("mon_modele", tokens_in=1000, tokens_out=1000)
        assert abs(c - 0.003) < 1e-9
    finally:
        costs.reset_costs()


def test_register_costs_preserves_defaults():
    costs.register_costs({"ephemere": (0.0, 0.0)})
    try:
        # gpt-4o reste accessible apres l override
        assert costs.get_cost("gpt-4o", tokens_in=1000, tokens_out=0) == 0.005
    finally:
        costs.reset_costs()