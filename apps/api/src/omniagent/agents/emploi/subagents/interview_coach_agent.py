"""Agent Interview Coach : prepare le candidat aux entretiens apres postulation.

Genere :
- une liste de questions probables basees sur l offre (mots-cles)
- un pitch personnel structure (30s / 90s / 3min)
- des points de vigilance a verifier avant l entretien
- des questions a poser au recruteur

Best-effort : heuristique sans LLM (mots-cles + templates). Si un LLM est
disponible cote appelant, le `prompt` est aussi expose pour integration.
"""
from __future__ import annotations

from typing import Any


# --- Templates de questions par categorie ---
QUESTION_BANK: dict[str, list[str]] = {
    "tech": [
        "Decris un projet technique recent ou tu as eu un impact mesurable.",
        "Comment debuggues-tu un probleme de production sous stress ?",
        "Quelle est ta preference entre dette technique assumee et refacto systematique ?",
        "Comment geres-tu le compromis entre vitesse de livraison et qualite ?",
    ],
    "data": [
        "Comment assures-tu la qualite d un pipeline de donnees ?",
        "Quelle est ta methode pour detecter un drift sur un modele ML ?",
        "Comment presentes-tu des resultats statistiques a un public non technique ?",
        "Donne un exemple ou tes analyses ont change une decision business.",
    ],
    "product": [
        "Comment priorises-tu des features avec des stakeholders contradictoires ?",
        "Quelle est ta plus grosse erreur produit et qu en as-tu tire ?",
        "Comment mesures-tu le succes d une feature en production ?",
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


def _detect_category(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ["data", "ml", "modele", "pipeline", "sql", "analytics"]):
        return "data"
    if any(k in t for k in ["react", "django", "fastapi", "kubernetes", "aws", "backend", "frontend"]):
        return "tech"
    if any(k in t for k in ["product", "roadmap", "stakeholder", "metric"]):
        return "product"
    return "general"


async def run(input_data: dict, user_id: str) -> dict:
    """Genere le kit de preparation a l entretien.

    input_data attendu :
        - offer: dict (title, company, description, ...)
        - profile: dict (full_name, skills, experiences, ...)
    Retourne : dict avec questions, pitch, red_flags, questions_to_ask
    """
    offer = input_data.get("offer") or {}
    profile = input_data.get("profile") or {}
    category = _detect_category(offer.get("description", "") + " " + offer.get("title", ""))

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

    # Filtrage des red flags : si l offre contient un salaire explicite -> pas un red flag
    red_flags = list(RED_FLAGS)
    if offer.get("salary"):
        red_flags = [r for r in red_flags if "salaire" not in r.lower()]

    return {
        "agent": "agent_interview_coach",
        "user_id": user_id,
        "offer_title": offer.get("title"),
        "company": offer.get("company"),
        "category": category,
        "questions": QUESTION_BANK[category] + QUESTION_BANK["general"],
        "pitch": {
            "30s": pitch_30s,
            "90s": pitch_90s,
            "3min": pitch_3min,
        },
        "red_flags": red_flags,
        "questions_to_ask": QUESTIONS_TO_ASK,
        "status": "ready",
    }