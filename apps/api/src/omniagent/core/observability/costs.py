"""Table de couts LLM (USD par 1k tokens, input + output).

But : estimer le cout d un run d agent a partir du modele et des tokens consommes.
Pas une verite comptable : c est un barme par defaut, surchargeable.

Comment l utiliser :
    from omniagent.core.observability.costs import get_cost
    cost = get_cost("gpt-4o", tokens_in=1200, tokens_out=300)

Comment l etendre :
    - ajouter une entree dans MODEL_COSTS (ci-dessous)
    - ou appeler register_costs({...}) au demarrage (ex: depuis settings)
"""
from __future__ import annotations
from typing import Mapping

# Cout par defaut, en USD par 1k tokens : (input, output).
# Les valeurs sont des approximations 2024-2025, a raffiner avec la vraie grille tarifaire.
MODEL_COSTS: dict[str, tuple[float, float]] = {
    "gpt-4o":              (0.005, 0.015),
    "gpt-4o-mini":         (0.00015, 0.0006),
    "gpt-4.1":             (0.01, 0.03),
    "gpt-4.1-mini":        (0.0004, 0.0016),
    "claude-sonnet":       (0.003, 0.015),
    "claude-haiku":        (0.00025, 0.00125),
    "claude-opus":         (0.015, 0.075),
    "mock":                (0.0, 0.0),       # pour les agents qui ne font pas de LLM reel
    "unknown":             (0.0, 0.0),       # fallback : on ne sait pas, on compte 0
}

# Permet a un consommateur (settings, test, plugin) d ajouter ou override.
_custom_costs: dict[str, tuple[float, float]] = {}


def register_costs(costs: Mapping[str, tuple[float, float]]) -> None:
    """Override ou ajout de barme. Utile depuis settings ou un plugin."""
    for k, v in costs.items():
        _custom_costs[k] = v


def reset_costs() -> None:
    """Reinitialise les overrides (utile en tests)."""
    _custom_costs.clear()


def _resolve(model: str) -> tuple[float, float]:
    if model in _custom_costs:
        return _custom_costs[model]
    if model in MODEL_COSTS:
        return MODEL_COSTS[model]
    return MODEL_COSTS["unknown"]


def get_cost(model: str, tokens_in: int = 0, tokens_out: int = 0) -> float:
    """Cout total USD pour un run ayant consomme tokens_in input + tokens_out output.

    Si model est inconnu, on retourne 0.0 (on n invente pas un prix).
    """
    in_rate, out_rate = _resolve(model)
    return (max(tokens_in, 0) / 1000.0) * in_rate + (max(tokens_out, 0) / 1000.0) * out_rate