"""Agent Salary Benchmark : noeud DAG.

Entree :
  input_data = {
    "step": {...},
    "context": {...},
    "previous": {"interview_prep": <output du noeud precedent>},
    "user_id": str,
    "role": str,
    "city": str,
    "years_experience": int,
    "declared_salary": float | None,
    "offer_salary": float | None,  # si fourni, on evalue l offre
    "match_score": float | None,   # 0-1, recu du noeud interview_prep
  }

Sortie :
  {
    "agent": "agent_salary_benchmark",
    "user_id": str,
    "node_id": "salary",
    "status": "ok",
    "inputs_consumed": ["role", "city", "years_experience", "previous.match_score"],
    "outputs_produced": {
      "range_keur": {"min": float, "median": float, "max": float},
      "market_position": "below_market|in_market|above_market",
      "offer_vs_market": "below_market|in_market|above_market|unknown",
      "negotiation_leverage": float (0-1, plus c est haut plus on peut negocier),
      "recommended_counter_offer_keur": float | None,
      "arguments": [str],
      "context_aware": {match_score_adjustment: float, ...},
    },
  }
"""
from __future__ import annotations

from typing import Any


GRID: dict[str, dict[str, tuple[int, int]]] = {
    "data scientist": {"paris": (42, 58), "lyon": (38, 52), "toulouse": (36, 50), "default": (36, 50)},
    "data engineer": {"paris": (45, 62), "lyon": (40, 55), "default": (40, 55)},
    "ml engineer":    {"paris": (50, 70), "default": (45, 65)},
    "backend developer":   {"paris": (40, 58), "lyon": (36, 52), "default": (36, 50)},
    "frontend developer":  {"paris": (38, 54), "default": (34, 48)},
    "fullstack developer": {"paris": (40, 56), "default": (36, 50)},
    "devops engineer":     {"paris": (45, 62), "default": (42, 58)},
    "product manager":     {"paris": (50, 70), "default": (45, 62)},
    "stage data":    {"default": (18, 24)},
    "alternance data": {"default": (24, 32)},
}

XP_MULTIPLIER: list[tuple[int, float]] = [
    (0, 0.85), (2, 1.0), (5, 1.15), (10, 1.30), (99, 1.45),
]


def _norm_role(role: str) -> str:
    r = (role or "").lower()
    if "data scientist" in r or "data science" in r: return "data scientist"
    if "data engineer" in r or "ingenieur donnees" in r: return "data engineer"
    if "ml" in r or "machine learning" in r: return "ml engineer"
    if "backend" in r: return "backend developer"
    if "frontend" in r: return "frontend developer"
    if "fullstack" in r or "full-stack" in r: return "fullstack developer"
    if "devops" in r or "sre" in r or "platform" in r: return "devops engineer"
    if "product" in r and "manager" in r: return "product manager"
    if "stage" in r or "intern" in r: return "stage data"
    if "alternance" in r or "apprentice" in r: return "alternance data"
    return "backend developer"


def _norm_city(city: str) -> str:
    c = (city or "").lower()
    if "paris" in c: return "paris"
    if "lyon" in c: return "lyon"
    if "toulouse" in c: return "toulouse"
    return "default"


def _xp_multiplier(years: int) -> float:
    y = max(0, years)
    for threshold, mult in XP_MULTIPLIER:
        if y <= threshold:
            return mult
    return 1.45


async def run(input_data: dict, user_id: str) -> dict:
    """Noeud DAG : benchmark salarial + recommandation de contre-offre."""
    role = _norm_role(input_data.get("role") or "")
    city = _norm_city(input_data.get("city") or "")
    years = int(input_data.get("years_experience") or 0)
    declared = input_data.get("declared_salary")
    offer_salary = input_data.get("offer_salary")
    previous = input_data.get("previous") or {}

    # Cross-node input : on peut recevoir le match_score du noeud interview
    match_score = input_data.get("match_score")
    if match_score is None and "interview_prep" in previous:
        prev_output = previous["interview_prep"]
        if isinstance(prev_output, dict):
            nested = prev_output.get("outputs_produced") or prev_output
            match_score = nested.get("match_score")

    base = GRID.get(role, {}).get(city) or GRID.get(role, {}).get("default", (35, 50))
    mult = _xp_multiplier(years)
    lo = round(base[0] * mult, 1)
    hi = round(base[1] * mult, 1)
    median = round((lo + hi) / 2, 1)

    # Ajustement par match_score : si on est tres aligne, on peut viser le haut
    adjustment = 0.0
    if match_score is not None:
        # score 0.5 -> 0, score 1.0 -> +5% sur le median
        adjustment = max(-0.05, min(0.05, (match_score - 0.5) * 0.10))
        median = round(median * (1 + adjustment), 1)
        hi = round(hi * (1 + adjustment * 0.5), 1)

    # Position du candidat vs marche
    declared_status = None
    declared_index = None
    if isinstance(declared, (int, float)) and declared > 0:
        if declared < lo: declared_status = "below_market"
        elif declared > hi: declared_status = "above_market"
        else: declared_status = "in_market"
        declared_index = round(declared / median, 2)

    # Position de l offre vs marche
    offer_status = "unknown"
    if isinstance(offer_salary, (int, float)) and offer_salary > 0:
        if offer_salary < lo: offer_status = "below_market"
        elif offer_salary > hi: offer_status = "above_market"
        else: offer_status = "in_market"

    # Levier de negociation : 0.5 base, +0.3 si offre sous le marche, +0.2 si match > 0.7
    leverage = 0.3  # base
    if offer_status == "below_market": leverage += 0.4
    if match_score is not None and match_score >= 0.7: leverage += 0.2
    leverage = round(min(1.0, leverage), 2)

    # Contre-offre recommandee : median + ajustement selon leverage
    counter_offer = None
    if isinstance(offer_salary, (int, float)) and offer_salary > 0 and offer_status != "in_market":
        # Si l offre est sous le marche : viser median+10% (max possible raisonnable)
        if offer_status == "below_market":
            counter_offer = round(median * 1.05, 1)
        # Si l offre est au-dessus : on accepte mais on demande du non-salarial
        # (pas de contre-proposition salariale a la hausse)

    # Arguments adaptatifs
    arguments = [
        f"Fourchette marche pour {role} a {city} : {lo}-{hi} KEUR (median {median}).",
        f"Votre profil ({years} ans d experience) justifie le multiplicateur x{mult}.",
    ]
    if match_score is not None:
        arguments.append(f"Votre match avec l offre est de {match_score:.2f} : " +
                         ("vous etes dans le haut du panier, vous pouvez negocier fermement." if match_score >= 0.7
                          else "match moyen, insistez sur les autres avantages."))
    if offer_status == "below_market":
        arguments.append(
            f"L offre proposee ({offer_salary} KEUR) est sous le marche : "
            "argument de negociation legitime a presenter avec des donnees a l appui."
        )
    elif offer_status == "above_market":
        arguments.append(
            "L offre est au-dessus du median : vous pouvez accepter sereinement "
            "ou negocier des avantages non-salariaux (teletravail, RTT, formation)."
        )
    if declared_status == "below_market":
        arguments.append(
            f"Votre remuneration actuelle ({declared} KEUR) est sous le marche : "
            "vous etes en position de force pour augmenter."
        )

    return {
        "agent": "agent_salary_benchmark",
        "user_id": user_id,
        "node_id": "salary",
        "status": "ok",
        "inputs_consumed": ["role", "city", "years_experience", "declared_salary"],
        "outputs_produced": {
            "range_keur": {"min": lo, "median": median, "max": hi},
            "market_position": declared_status or "unknown",
            "offer_vs_market": offer_status,
            "match_score_used": match_score,
            "negotiation_leverage": leverage,
            "recommended_counter_offer_keur": counter_offer,
            "arguments": arguments,
        },
        # Champs top-level (compat)
        "role_normalized": role,
        "city_normalized": city,
        "years_experience": years,
        "xp_multiplier": mult,
        "range_keur": {"min": lo, "median": median, "max": hi},
        "declared_salary_keur": declared,
        "declared_status": declared_status,
        "declared_index": declared_index,
        "negotiation_arguments": arguments,
        "source": "internal_grid_2025",
        "caveat": "Grille indicative. Pour un vrai benchmark, brancher Glassdoor/Indeed/Levels.fyi.",
    }