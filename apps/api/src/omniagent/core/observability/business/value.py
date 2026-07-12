"""Heuristiques de business_value par agent (module -> extraction depuis l output).

But : transformer le dict retourne par un sub-agent en une valeur metier
exploitable par le dashboard.

Conventions (cote sub-agent, dans le dict retourne par `run(input_data, user_id)`) :
  - agent_emploi_*      : out.get("applications_sent", 0)
  - agent_marketing_*   : out.get("posts_generated", 0)
  - agent_recouvrement_*: out.get("amount_collected", 0.0)
  - fallback            : out.get("value", 0) (cle generique)

Si l output n est pas un dict (str, None...), on renvoie 0.0.
"""
from __future__ import annotations
from typing import Any, Callable

ValueExtractor = Callable[[Any], float]


def _count_or_zero(out: Any, key: str) -> float:
    if not isinstance(out, dict):
        return 0.0
    v = out.get(key, 0)
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _value_emploi(out: Any) -> float:
    return _count_or_zero(out, "applications_sent")


def _value_marketing(out: Any) -> float:
    return _count_or_zero(out, "posts_generated")


def _value_recouvrement(out: Any) -> float:
    return _count_or_zero(out, "amount_collected")


def _value_fallback(out: Any) -> float:
    """Fallback : cle `value` generique, ou 0."""
    return _count_or_zero(out, "value")


# Sous-chaînes (insensible a la position) -> module metier -> extracteur.
# L ordre compte : la premiere regle qui matche gagne. On commence par les
# sous-chaînes specifiques, puis on finit par le fallback `agent_` qui prend
# la cle generique `value`.
MODULE_VALUE_RULES: list[tuple[str, ValueExtractor]] = [
    # Emploi (candidatures envoyees)
    ("emploi",            _value_emploi),
    ("linkedin",          _value_emploi),
    ("indeed",            _value_emploi),
    ("hellowork",         _value_emploi),
    ("cv",                _value_emploi),
    ("lettre",            _value_emploi),
    # Marketing (contenus generes)
    ("marketing",         _value_marketing),
    ("instagram",         _value_marketing),
    ("tiktok",            _value_marketing),
    ("agent_x",           _value_marketing),  # X / Twitter
    # Recouvrement (€ recuperes)
    ("recouvrement",      _value_recouvrement),
    ("analyse_impayes",   _value_recouvrement),
    ("communication",     _value_recouvrement),
    ("vocal",             _value_recouvrement),
    # Fallback : cle `value` generique
    ("agent_",            _value_fallback),
]


def compute_business_value(agent_name: str, output: Any) -> float:
    """Calcule la business_value d un run a partir de l output du sub-agent.

    Matching par sous-chaine : la premiere regle qui matche `agent_name` gagne.
    Retourne 0.0 si aucune regle ne match ou si l extraction echoue.
    """
    for needle, extractor in MODULE_VALUE_RULES:
        if needle in agent_name:
            return extractor(output)
    return 0.0
