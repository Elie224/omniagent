"""Agent Followup : relance automatique des candidatures envoyees.

Strategies :
- genere un email de relance J+5 / J+10 / J+15 apres envoi
- choisit le ton selon le contexte (formel / decontracte / direct)
- propose un sujet et un corps courts
- signale les candidatures sans reponse depuis > 21 jours

Best-effort : generation par templates + heuristique. Integration future avec
un LLM ou un service d envoi (SendGrid) pour declenchement automatique.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


SUBJECTS_BY_TONE: dict[str, list[str]] = {
    "formel": [
        "Suite a ma candidature du {date} - point d avancement",
        "Relance concernant le poste de {role}",
        "Mon interet pour le poste de {role} chez {company}",
    ],
    "decontracte": [
        "Hello {company} - ou en est-on ?",
        "Petit mot sur ma candidature",
        "On se dit quoi sur {role} ?",
    ],
    "direct": [
        "Relance candidature {role}",
        "Status candidature - {company}",
        "Avancement processus {role}",
    ],
}

BODIES_BY_TONE: dict[str, list[str]] = {
    "formel": [
        "Bonjour,\n\nJe me permets de revenir vers vous suite a ma candidature au poste de {role}, envoyee le {date}. Je reste tres interesse par cette opportunite et serais ravi d echanger avec vous sur les prochaines etapes.\n\nBien cordialement,\n{name}",
    ],
    "decontracte": [
        "Salut,\n\nJe me doute que vous etes submerges, mais un petit retour sur ma candidature envoyee le {date} serait top. Je suis toujours partant pour discuter du poste de {role} !\n\nA bientot j espere,\n{name}",
    ],
    "direct": [
        "Bonjour,\n\nRelance pour ma candidature du {date} - poste {role}. Merci de me faire un point sur le statut.\n\n{name}",
    ],
}


def _pick(tone: str, role: str, company: str, name: str, sent_date: str) -> dict:
    """Selectionne un (subject, body) selon le ton."""
    import random
    subjects = SUBJECTS_BY_TONE.get(tone, SUBJECTS_BY_TONE["formel"])
    bodies = BODIES_BY_TONE.get(tone, BODIES_BY_TONE["formel"])
    subject = random.choice(subjects).format(role=role, company=company, date=sent_date)
    body = random.choice(bodies).format(role=role, company=company, date=sent_date, name=name)
    return {"subject": subject, "body": body}


def _days_since(sent_at: str) -> int:
    """Retourne le nombre de jours depuis sent_at (ISO 8601)."""
    if not sent_at:
        return 0
    try:
        if isinstance(sent_at, str):
            dt = datetime.fromisoformat(sent_at.replace("Z", "+00:00"))
        else:
            dt = sent_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return max(0, (now - dt).days)
    except Exception:
        return 0


async def run(input_data: dict, user_id: str) -> dict:
    """Genere des relances pour une liste de candidatures.

    input_data :
        - applications: list[dict]   -> chaque dict doit contenir
            company, position, sent_at (ISO), contact_name
        - profile: dict             -> full_name
        - tone: str                 -> formel | decontracte | direct (default formel)
        - threshold_days: int       -> declenche relance si J > threshold (default 5)
    """
    profile = input_data.get("profile") or {}
    name = profile.get("full_name") or user_id
    tone = input_data.get("tone") or "formel"
    threshold = int(input_data.get("threshold_days") or 5)
    applications = input_data.get("applications") or []

    relances: list[dict] = []
    stale: list[dict] = []

    for app in applications:
        sent_at = app.get("sent_at") or ""
        days = _days_since(sent_at)
        company = app.get("company") or "?"
        role = app.get("position") or app.get("contract") or "poste"
        contact = app.get("contact_name") or "Madame, Monsieur"

        if days >= threshold:
            msg = _pick(tone, role, company, name, sent_at[:10] if sent_at else "recemment")
            relances.append({
                "application_id": app.get("id"),
                "company": company,
                "position": role,
                "days_since_sent": days,
                "to": contact,
                "urgency": "high" if days >= 21 else ("medium" if days >= 14 else "low"),
                **msg,
            })
        if days >= 21:
            stale.append({
                "application_id": app.get("id"),
                "company": company,
                "days_since_sent": days,
                "suggestion": "Considerer abandon ou derniere relance directe.",
            })

    return {
        "agent": "agent_followup",
        "user_id": user_id,
        "tone": tone,
        "threshold_days": threshold,
        "relances_generated": len(relances),
        "stale_count": len(stale),
        "relances": relances,
        "stale_applications": stale,
        "status": "ok",
        "caveat": "Generation automatique. Verification humaine recommandee avant envoi.",
    }