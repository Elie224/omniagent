"""Agent Followup : noeud DAG.

Entree :
  input_data = {
    "step": {...},
    "context": {...},
    "previous": {"interview_prep": ..., "salary": ...},
    "user_id": str,
    "applications": list[dict],
    "profile": dict,
    "tone": str,
    "threshold_days": int,
  }

Sortie :
  {
    "agent": "agent_followup",
    "user_id": str,
    "node_id": "followup",
    "status": "ok",
    "inputs_consumed": ["applications", "previous.interview_prep.match_score", "previous.salary.offer_vs_market"],
    "outputs_produced": {
      "plan": [{application_id, action, days_since_sent, ...}, ...],
      "next_action_date": str (ISO),
      "kpis": {total_apps, needs_relance, stale, urgent},
      "strategy_summary": str,
    },
  }
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

# Strategie : on choisit le ton selon l'urgence
TONE_BY_URGENCY = {
    "urgent": "direct",        # > 21 jours, on est direct
    "high": "formel",          # 14-21 jours
    "medium": "formel",        # 7-14 jours
    "low": "decontracte",      # 5-7 jours, on est leger
}


def _pick(tone: str, role: str, company: str, name: str, sent_date: str) -> dict:
    import random
    subjects = SUBJECTS_BY_TONE.get(tone, SUBJECTS_BY_TONE["formel"])
    bodies = BODIES_BY_TONE.get(tone, BODIES_BY_TONE["formel"])
    subject = random.choice(subjects).format(role=role, company=company, date=sent_date)
    body = random.choice(bodies).format(role=role, company=company, date=sent_date, name=name)
    return {"subject": subject, "body": body}


def _days_since(sent_at: str) -> int:
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


def _urgency_level(days: int) -> str:
    if days >= 21: return "urgent"
    if days >= 14: return "high"
    if days >= 7:  return "medium"
    return "low"


async def run(input_data: dict, user_id: str) -> dict:
    """Noeud DAG : plan de relance orchestre (cross-noeuds)."""
    profile = input_data.get("profile") or {}
    name = profile.get("full_name") or user_id
    default_tone = input_data.get("tone") or "formel"
    threshold = int(input_data.get("threshold_days") or 5)
    applications = input_data.get("applications") or []
    previous = input_data.get("previous") or {}

    # Cross-node inputs : on recupere le contexte des noeuds precedents
    interview_out = previous.get("interview_prep")
    if isinstance(interview_out, dict):
        interview_data = interview_out.get("outputs_produced") or interview_out
        match_score = interview_data.get("match_score")
    else:
        match_score = None

    salary_out = previous.get("salary")
    offer_vs_market = None
    leverage = None
    if isinstance(salary_out, dict):
        salary_data = salary_out.get("outputs_produced") or salary_out
        offer_vs_market = salary_data.get("offer_vs_market")
        leverage = salary_data.get("negotiation_leverage")

    plan: list[dict] = []
    stale: list[dict] = []
    needs_relance_count = 0
    urgent_count = 0

    today = datetime.now(timezone.utc).date()

    for app in applications:
        sent_at = app.get("sent_at") or ""
        days = _days_since(sent_at)
        company = app.get("company") or "?"
        role = app.get("position") or app.get("contract") or "poste"
        contact = app.get("contact_name") or "Madame, Monsieur"

        urgency = _urgency_level(days)

        if days >= threshold:
            needs_relance_count += 1
            if urgency in ("urgent", "high"):
                urgent_count += 1
            # Choix du ton : si on a un match_score haut ou une offre sous le marche,
            # on garde le ton formel (on est confiant). Sinon adaptatif.
            if match_score is not None and match_score >= 0.7:
                tone = "formel"
            elif offer_vs_market == "below_market":
                tone = "direct"  # on a des arguments, on est cash
            else:
                tone = TONE_BY_URGENCY[urgency]
            msg = _pick(tone, role, company, name, sent_at[:10] if sent_at else "recemment")
            next_date = today + timedelta(days=3 if urgency == "urgent" else 5)
            plan.append({
                "application_id": app.get("id"),
                "company": company,
                "position": role,
                "days_since_sent": days,
                "urgency": urgency,
                "tone_used": tone,
                "to": contact,
                "next_action_date": next_date.isoformat(),
                "action": "relance_email",
                **msg,
            })
        if days >= 21:
            stale.append({
                "application_id": app.get("id"),
                "company": company,
                "days_since_sent": days,
                "suggestion": "Considerer abandon ou derniere relance directe.",
            })

    # Strategie globale : on prend en compte le contexte
    strategy_parts = [f"{len(applications)} candidature(s) suivies."]
    if match_score is not None:
        strategy_parts.append(f"Match score moyen avec les offres : {match_score:.2f}.")
    if offer_vs_market == "below_market":
        strategy_parts.append("Les offres sont sous le marche : ton direct recommande.")
    elif offer_vs_market == "above_market":
        strategy_parts.append("Les offres sont au-dessus du marche : flexibilite sur le timing.")
    if leverage is not None and leverage >= 0.7:
        strategy_parts.append("Levier de negociation eleve : vous pouvez vous permettre d etre ferme.")
    strategy = " ".join(strategy_parts)

    # Date de la prochaine action globale = la plus proche du plan
    next_action_date = None
    if plan:
        next_action_date = min(p["next_action_date"] for p in plan)

    return {
        "agent": "agent_followup",
        "user_id": user_id,
        "node_id": "followup",
        "status": "ok",
        "inputs_consumed": ["applications", "previous.interview_prep", "previous.salary"],
        "outputs_produced": {
            "plan": plan,
            "next_action_date": next_action_date,
            "kpis": {
                "total_apps": len(applications),
                "needs_relance": needs_relance_count,
                "stale": len(stale),
                "urgent": urgent_count,
            },
            "strategy_summary": strategy,
        },
        # Champs top-level (compat smoke tests)
        "tone": default_tone,
        "threshold_days": threshold,
        "relances_generated": len(plan),
        "stale_count": len(stale),
        "relances": plan,
        "stale_applications": stale,
        "caveat": "Generation automatique. Verification humaine recommandee avant envoi.",
    }