"""Agent Interview Coach : noeud DAG.

Entree :
  input_data = {
    "step": {"role_context": "data|tech|product|general", "depth": "standard|deep"},
    "context": { ... contexte global du workflow ... },
    "previous": { ... outputs des steps precedents ... },
    "user_id": str,
    "offer": { title, company, description, location, contract, salary, ... },
    "profile": { full_name, email, phone, city, skills, experiences, target_roles, ... },
  }

Sortie :
  {
    "agent": "agent_interview_coach",
    "user_id": str,
    "node_id": "interview_prep",
    "status": "ready",
    "inputs_consumed": ["offer", "profile"],
    "outputs_produced": {
      "questions": [...],
      "pitch": {"30s": str, "90s": str, "3min": str},
      "red_flags": [...],
      "questions_to_ask": [...],
      "match_score": float (0-1),       # scoring real : compatibilite profil/offre
      "key_themes": [str],              # themes extraits de l offre pour chainage
      "strengths_to_highlight": [str],  # points forts du profil a mettre en avant
      "weaknesses_to_address": [str],   # points faibles a anticiper
    },
  }
"""
from __future__ import annotations

import re
from typing import Any


QUESTION_BANK: dict[str, list[str]] = {
    "tech": [
        "Decris un projet technique recent ou tu as eu un impact mesurable.",
        "Comment debuggues-tu un probleme de production sous stress ?",
        "Quelle est ta preference entre dette technique assumee et refacto systematique ?",
        "Comment geres-tu le compromis entre vitesse de livraison et qualite ?",
        "Comment fais-tu evoluer une API sans casser les consommateurs ?",
    ],
    "data": [
        "Comment assures-tu la qualite d un pipeline de donnees ?",
        "Quelle est ta methode pour detecter un drift sur un modele ML ?",
        "Comment presentes-tu des resultats statistiques a un public non technique ?",
        "Donne un exemple ou tes analyses ont change une decision business.",
        "Comment evalues-tu la fiabilite d une source de donnees tiers ?",
    ],
    "product": [
        "Comment priorises-tu des features avec des stakeholders contradictoires ?",
        "Quelle est ta plus grosse erreur produit et qu en as-tu tire ?",
        "Comment mesures-tu le succes d une feature en production ?",
        "Comment articules-tu les OKR avec les Equipes Tech et Design ?",
    ],
    "general": [
        "Pourquoi cette entreprise plutot qu une autre ?",
        "Ou te vois-tu dans 3 ans ?",
        "Quel est ton plus gros echec professionnel et qu as-tu appris ?",
        "Pourquoi quittes-tu (ou quitterais-tu) ton poste actuel ?",
        "Quel est ton preavis ?",
    ],
}

RED_FLAGS: list[str] = [
    "Offre avec salaire non communique",
    "Description vague des responsabilites",
    "Process de recrutement > 4 etapes",
    "Pas de temps de reponse defini",
    "Demande de travail gratuit (test technique > 4h)",
]

QUESTIONS_TO_ASK: list[str] = [
    "Quel est le contexte de l equipe (taille, maturite, stack) ?",
    "Quels sont les objectifs des 3 premiers mois ?",
    "Comment se deroule le suivi de performance ?",
    "Quel est le budget formation / conference ?",
    "Pourquoi le poste est-il ouvert (croissance, remplacement, creation) ?",
]


# Mots-cles par theme (utilises pour extraire des key_themes et matcher le profil)
THEME_KEYWORDS: dict[str, list[str]] = {
    "python": ["python", "django", "flask", "fastapi", "pandas", "numpy"],
    "sql": ["sql", "postgres", "mysql", "bigquery", "snowflake"],
    "ml": ["machine learning", "ml", "modele", "sklearn", "pytorch", "tensorflow"],
    "cloud": ["aws", "gcp", "azure", "kubernetes", "docker", "terraform"],
    "data_viz": ["tableau", "power bi", "looker", "metabase", "dashboards"],
    "etl": ["etl", "elt", "airflow", "dbt", "spark", "data engineering"],
    "product": ["product manager", "product owner", "roadmap produit", "stakeholder", "okr"],
    "leadership": ["management", "lead", "mentor", "equipe", "leadership"],
    "french_required": ["francais", "fluide", "bilingue"],
    "english_required": ["english", "anglais", "fluent"],
}


def _detect_category(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ["data", "ml", "modele", "pipeline", "sql", "analytics"]):
        return "data"
    if any(k in t for k in ["react", "django", "fastapi", "kubernetes", "aws", "backend", "frontend"]):
        return "tech"
    if any(k in t for k in ["product", "roadmap", "stakeholder", "metric"]):
        return "product"
    return "general"


def _extract_themes(text: str) -> list[str]:
    """Extrait les themes techniques/domaines d un texte (utilise pour chainage)."""
    found = []
    t = (text or "").lower()
    for theme, kws in THEME_KEYWORDS.items():
        if any(kw in t for kw in kws):
            found.append(theme)
    return found


def _match_score(profile: dict, offer: dict, themes: list[str]) -> float:
    """Score de compatibilite 0-1 entre profil et offre.

    Methode :
    - skills profil vs themes de l offre : 60% du score
    - ville du profil vs localisation de l offre : 20%
    - type de contrat : 10%
    - experience vs niveau demande (fallback si non specifie) : 10%
    """
    score = 0.0

    # Skills match
    profile_skills = set((s.lower() for s in (profile.get("skills") or [])))
    if profile_skills and themes:
        themes_skills = set()
        for theme in themes:
            for kw in THEME_KEYWORDS.get(theme, []):
                themes_skills.add(kw)
        if themes_skills:
            inter = len(profile_skills & themes_skills)
            score += 0.6 * min(1.0, inter / max(1, len(themes)))

    # Location match
    offer_loc = (offer.get("location") or "").lower()
    profile_city = (profile.get("city") or "").lower()
    if offer_loc and profile_city:
        if profile_city in offer_loc or offer_loc in profile_city or "france" in offer_loc:
            score += 0.2
    elif not offer_loc:
        score += 0.1  # pas de localisation exigee

    # Contract match
    profile_targets = [t.lower() for t in (profile.get("target_roles") or [])]
    offer_contract = (offer.get("contract") or "").lower()
    if profile_targets and offer_contract:
        if any(ct in t or t in ct for t in profile_targets for ct in [offer_contract]):
            score += 0.1
    elif not offer_contract:
        score += 0.05

    # Experience (heuristique : on accorde le max si pas de niveau exige)
    score += 0.1  # bonus fixe (manque de spec d experience cote offre)

    return round(min(1.0, score), 3)


def _build_strengths(profile: dict, themes: list[str]) -> list[str]:
    """Liste les points forts du profil alignes avec les themes de l offre."""
    strengths = []
    skills = set(s.lower() for s in (profile.get("skills") or []))
    for theme in themes:
        theme_kws = THEME_KEYWORDS.get(theme, [])
        matched = [s for s in skills for kw in theme_kws if kw in s]
        if matched:
            strengths.append(f"Maitrise {theme}: {', '.join(sorted(set(matched))[:3])}")
    if profile.get("experiences"):
        strengths.append(f"{len(profile['experiences'])} experience(s) professionnelle(s)")
    return strengths[:5]


def _build_weaknesses(profile: dict, themes: list[str]) -> list[str]:
    """Identifie les manques entre profil et offre pour preparer le candidat."""
    weaknesses = []
    skills = set(s.lower() for s in (profile.get("skills") or []))
    for theme in themes:
        theme_kws = THEME_KEYWORDS.get(theme, [])
        if not any(kw in s for s in skills for kw in theme_kws):
            weaknesses.append(f"Pas de trace de {theme} dans le profil -> preparer une reponse")
    return weaknesses[:5]


async def run(input_data: dict, user_id: str) -> dict:
    """Noeud DAG : preparation d entretien contextuelle."""
    offer = input_data.get("offer") or {}
    profile = input_data.get("profile") or {}
    step_cfg = input_data.get("step") or {}
    ctx = input_data.get("context") or {}
    previous = input_data.get("previous") or {}

    # Si l appel vient du workflow post_application, on a un previous vide
    # (premier step). On accepte aussi un appel direct via la route API.

    text_to_categorize = (offer.get("description", "") or "") + " " + (offer.get("title", "") or "")
    category = step_cfg.get("role_context") or _detect_category(text_to_categorize)
    themes = _extract_themes(text_to_categorize)
    score = _match_score(profile, offer, themes)

    # Pitch structure : 30s / 90s / 3min
    name = profile.get("full_name") or "Candidat"
    target = (offer.get("title") or "poste vise").strip()
    skills = profile.get("skills") or []
    experiences = profile.get("experiences") or []
    last_exp = experiences[0] if experiences else {}

    pitch_30s = (
        f"Bonjour, je m appelle {name}. Je postule pour le poste de {target}. "
        f"J apporte {len(skills)} competences cles dont " +
        (", ".join(skills[:3]) if skills else "une solide experience metier") +
        "."
    )
    pitch_90s = pitch_30s + (
        f" Recemment, j ai travaille chez {last_exp.get('company', 'ma precedente entreprise')} "
        f"ou j ai {last_exp.get('description', 'contribue a des livrables a forte valeur')}. "
        "Je cherche un environnement ou je peux mettre a profit ces competences tout en progressant."
    )
    pitch_3min = pitch_90s + (
        " Sur le plan technique, je maitrise " +
        (", ".join(skills[:5]) if len(skills) >= 5 else "les fondamentaux du domaine") +
        ". Sur le plan humain, je privilegie la collaboration, la clarity du code, "
        "et un equilibre entre execution rapide et qualite. "
        f"C est pourquoi {offer.get('company', 'votre entreprise')} m attire particulierement."
    )

    red_flags = list(RED_FLAGS)
    if offer.get("salary"):
        red_flags = [r for r in red_flags if "salaire" not in r.lower()]

    strengths = _build_strengths(profile, themes)
    weaknesses = _build_weaknesses(profile, themes)

    return {
        "agent": "agent_interview_coach",
        "user_id": user_id,
        "node_id": "interview_prep",
        "status": "ready",
        "inputs_consumed": ["offer", "profile"],
        "outputs_produced": {
            "offer_title": offer.get("title"),
            "company": offer.get("company"),
            "category": category,
            "themes": themes,
            "match_score": score,
            "questions": QUESTION_BANK[category] + QUESTION_BANK["general"],
            "pitch": {
                "30s": pitch_30s,
                "90s": pitch_90s,
                "3min": pitch_3min,
            },
            "red_flags": red_flags,
            "questions_to_ask": QUESTIONS_TO_ASK,
            "strengths_to_highlight": strengths,
            "weaknesses_to_address": weaknesses,
        },
        # Champs top-level pour compatibilite ascendante (smoke tests existants)
        "category": category,
        "questions": QUESTION_BANK[category] + QUESTION_BANK["general"],
        "pitch": {
            "30s": pitch_30s,
            "90s": pitch_90s,
            "3min": pitch_3min,
        },
        "red_flags": red_flags,
        "questions_to_ask": QUESTIONS_TO_ASK,
    }