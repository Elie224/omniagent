"""Agent Lettre Requirement : genere la lettre seulement si l'offre l'exige."""
from __future__ import annotations

import re
from typing import Any


_REQUIRED_PATTERNS = [
    r"lettre\s+de\s+motivation",
    r"lm\s+obligatoire",
    r"cover\s+letter",
    r"motivation\s+letter",
    r"joindre\s+une\s+lettre",
    r"merci\s+de\s+joindre\s+votre\s+lettre",
]


def _text_for_detection(offer: dict[str, Any]) -> str:
    parts = [
        str(offer.get("title") or ""),
        str(offer.get("description") or ""),
        str(offer.get("requirements") or ""),
    ]
    return "\n".join(parts).lower()


def _is_letter_required(offer: dict[str, Any]) -> bool:
    txt = _text_for_detection(offer)
    if not txt.strip():
        return False
    return any(re.search(p, txt, flags=re.IGNORECASE) for p in _REQUIRED_PATTERNS)


def _infer_contract(offer: dict[str, Any]) -> str:
    c = str(offer.get("contract") or "").lower()
    if "stage" in c:
        return "stage"
    if "altern" in c:
        return "alternance"
    return "emploi"


def _build_variables(profile: dict[str, Any], offer: dict[str, Any]) -> dict[str, str]:
    target_roles = profile.get("target_roles") or []
    role = str(offer.get("title") or (target_roles[0] if target_roles else "votre offre")).strip()
    return {
        "rh_name": str(offer.get("rh_name") or "Madame, Monsieur").strip(),
        "role": role or "votre offre",
        "company": str(offer.get("company") or "votre entreprise").strip() or "votre entreprise",
        "name": str(profile.get("full_name") or profile.get("name") or "Candidat").strip() or "Candidat",
        "formation": str(profile.get("formation") or "formation en cours").strip() or "formation en cours",
        "motivation": str(
            offer.get("motivation_hint")
            or "je suis motive(e) par cette opportunite et l'impact du poste"
        ).strip(),
        "experience": str(profile.get("experience") or "plusieurs annees").strip() or "plusieurs annees",
    }


async def run(input_data: dict, user_id: str) -> dict:
    offer = input_data.get("offer") or {}
    profile = input_data.get("profile") or {}

    required = _is_letter_required(offer)
    contract = _infer_contract(offer)

    if not required:
        return {
            "agent": "agent_lettre_requirement",
            "status": "skipped_not_required",
            "inputs_consumed": ["offer", "profile"],
            "outputs_produced": {
                "required": False,
                "reason": "offer_does_not_request_cover_letter",
                "letter": None,
            },
        }

    from omniagent.agents.emploi.subagents.lettre_agent import run as run_lettre

    variables = _build_variables(profile, offer)
    letter = await run_lettre({"contract": contract, "variables": variables}, user_id=user_id)

    return {
        "agent": "agent_lettre_requirement",
        "status": "generated",
        "inputs_consumed": ["offer", "profile"],
        "outputs_produced": {
            "required": True,
            "reason": "offer_mentions_cover_letter",
            "contract": contract,
            "letter": letter,
        },
    }
