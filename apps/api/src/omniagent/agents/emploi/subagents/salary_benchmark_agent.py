"""Agent Salary Benchmark : estimation salariale basee sur le marche FR.

Sources de donnees : grilles internes (heuristiques par role/localisation/annees).
Best-effort : pour un vrai benchmark, brancher une API externe (Glassdoor,
Indeed Salaries, Levels.fyi) via un connector.

Retourne :
- une fourchette min / median / max
- un indice vs salaire auto-declare
- des arguments de negociation
"""
from __future__ import annotations

from typing import Any


# Grille simplifiee (en KEUR brut annuel, France, 2025).
# Cle = (role, ville). role normalise en minuscules.
GRID: dict[str, dict[str, tuple[int, int]]] = {
    "data scientist": {
        "paris": (42, 58),
        "lyon": (38, 52),
        "toulouse": (36, 50),
        "default": (36, 50),
    },
    "data engineer": {
        "paris": (45, 62),
        "lyon": (40, 55),
        "default": (40, 55),
    },
    "ml engineer": {
        "paris": (50, 70),
        "default": (45, 65),
    },
    "backend developer": {
        "paris": (40, 58),
        "lyon": (36, 52),
        "default": (36, 50),
    },
    "frontend developer": {
        "paris": (38, 54),
        "default": (34, 48),
    },
    "fullstack developer": {
        "paris": (40, 56),
        "default": (36, 50),
    },
    "devops engineer": {
        "paris": (45, 62),
        "default": (42, 58),
    },
    "product manager": {
        "paris": (50, 70),
        "default": (45, 62),
    },
    "stage data": {"default": (18, 24)},
    "alternance data": {"default": (24, 32)},
}

# Multiplicateurs par annees d experience
XP_MULTIPLIER: list[tuple[int, float]] = [
    (0, 0.85),   # < 1 an
    (2, 1.0),    # 1-2 ans
    (5, 1.15),   # 3-5 ans
    (10, 1.30),  # 6-10 ans
    (99, 1.45),  # 10+ ans
]


def _norm_role(role: str) -> str:
    r = (role or "").lower()
    # Reduction simple pour matcher la grille
    if "data scientist" in r or "data science" in r:
        return "data scientist"
    if "data engineer" in r or "ingenieur donnees" in r:
        return "data engineer"
    if "ml" in r or "machine learning" in r:
        return "ml engineer"
    if "backend" in r:
        return "backend developer"
    if "frontend" in r:
        return "frontend developer"
    if "fullstack" in r or "full-stack" in r:
        return "fullstack developer"
    if "devops" in r or "sre" in r or "platform" in r:
        return "devops engineer"
    if "product" in r and "manager" in r:
        return "product manager"
    if "stage" in r or "intern" in r:
        return "stage data"
    if "alternance" in r or "apprentice" in r:
        return "alternance data"
    return "backend developer"  # fallback


def _norm_city(city: str) -> str:
    c = (city or "").lower()
    if "paris" in c:
        return "paris"
    if "lyon" in c:
        return "lyon"
    if "toulouse" in c:
        return "toulouse"
    return "default"


def _xp_multiplier(years: int) -> float:
    y = max(0, years)
    for threshold, mult in XP_MULTIPLIER:
        if y <= threshold:
            return mult
    return 1.45


async def run(input_data: dict, user_id: str) -> dict:
    """Estime la fourchette salariale pour (role, ville, experience).

    input_data :
        - role: str (ex: "Data Scientist")
        - city: str (ex: "Paris")
        - years_experience: int
        - declared_salary: int | None (KEUR) -> comparaison
    """
    role = _norm_role(input_data.get("role") or "")
    city = _norm_city(input_data.get("city") or "")
    years = int(input_data.get("years_experience") or 0)
    declared = input_data.get("declared_salary")

    base = GRID.get(role, {}).get(city)
    if base is None:
        base = GRID.get(role, {}).get("default", (35, 50))

    mult = _xp_multiplier(years)
    lo = round(base[0] * mult, 1)
    hi = round(base[1] * mult, 1)
    median = round((lo + hi) / 2, 1)

    # Comparaison au salaire declare
    declared_status = None
    declared_index = None
    if isinstance(declared, (int, float)) and declared > 0:
        if declared < lo:
            declared_status = "below_market"
        elif declared > hi:
            declared_status = "above_market"
        else:
            declared_status = "in_market"
        declared_index = round(declared / median, 2)

    # Arguments de negociation
    arguments = [
        f"Fourchette marche pour {role} a {city} : {lo}-{hi} KEUR (median {median}).",
        f"Votre profil ({years} ans d experience) justifie le multiplicateur x{mult}.",
    ]
    if declared_status == "below_market":
        arguments.append(
            f"L offre proposee ({declared} KEUR) est sous le marche : "
            "argument de negociation legitime a presenter avec des donnees a l appui."
        )
    elif declared_status == "above_market":
        arguments.append(
            "Votre remuneration actuelle est au-dessus du median : "
            "utilisez-la comme preuve de votre valeur, mais restez ouvert aux avantages non-salariaux."
        )

    return {
        "agent": "agent_salary_benchmark",
        "user_id": user_id,
        "role_normalized": role,
        "city_normalized": city,
        "years_experience": years,
        "xp_multiplier": mult,
        "range_keur": {"min": lo, "median": median, "max": hi},
        "declared_salary_keur": declared,
        "declared_status": declared_status,
        "declared_index": declared_index,
        "negotiation_arguments": arguments,
        "status": "ok",
        "source": "internal_grid_2025",
        "caveat": "Grille indicative. Pour un vrai benchmark, brancher Glassdoor/Indeed/Levels.fyi.",
    }