"""Agent Application Sender : envoie la candidature par email au recruteur."""
from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path
from typing import Any
import smtplib

from omniagent.core.config import settings


def _build_letter_payload(offer: dict[str, Any], profile: dict[str, Any], provided: dict[str, Any]) -> tuple[str, str]:
    subject = str((provided or {}).get("subject") or "").strip()
    body = str((provided or {}).get("body") or "").strip()
    if subject and body:
        return subject, body

    contract = str(offer.get("contract") or "emploi")
    if "stage" in contract.lower():
        contract = "stage"
    elif "altern" in contract.lower():
        contract = "alternance"
    else:
        contract = "emploi"

    role = str(offer.get("title") or "votre offre").strip() or "votre offre"
    company = str(offer.get("company") or "votre entreprise").strip() or "votre entreprise"
    name = str(profile.get("full_name") or profile.get("name") or "Candidat").strip() or "Candidat"

    # lettre_agent est async: on construit une lettre minimale synchrone ici.
    # Ici on prefere un fallback simple plutot que de coupler cette fonction a une boucle event.
    fallback_subject = f"Candidature {role} - {name}"
    fallback_body = (
        f"Bonjour,\n\n"
        f"Je vous contacte concernant l'offre {role} chez {company}.\n"
        f"Vous trouverez mon CV en piece jointe.\n\n"
        f"Cordialement,\n{name}"
    )
    return (subject or fallback_subject), (body or fallback_body)


def _resolve_generated_cv_path(user_id: str) -> Path:
    from omniagent.agents.emploi.subagents.cv_agent import TEMPLATE_DIR
    return Path(TEMPLATE_DIR) / f"{user_id}_cv.pdf"


def _smtp_ready() -> bool:
    return bool(settings.smtp_host and settings.smtp_from_email)


def _send_email(to_email: str, subject: str, body: str, user_id: str) -> dict[str, Any]:
    msg = EmailMessage()
    from_name = settings.smtp_from_name.strip() if settings.smtp_from_name else "OmniAgent"
    msg["From"] = f"{from_name} <{settings.smtp_from_email}>" if from_name else settings.smtp_from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    cv_path = _resolve_generated_cv_path(user_id)
    attachment_used = False
    if cv_path.exists():
        msg.add_attachment(cv_path.read_bytes(), maintype="application", subtype="pdf", filename="cv.pdf")
        attachment_used = True
    elif settings.application_sender_require_cv:
        raise RuntimeError("CV genere introuvable: envoi bloque par garde-fou")

    with smtplib.SMTP(settings.smtp_host, int(settings.smtp_port), timeout=15) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(msg)

    return {"attachment_used": attachment_used}


async def run(input_data: dict, user_id: str) -> dict:
    offer = input_data.get("offer") or {}
    profile = input_data.get("profile") or {}
    recruiter_email = str(input_data.get("recruiter_email") or "").strip()
    provided_letter = input_data.get("letter") or {}
    user_confirmed = bool(input_data.get("user_confirmed") or False)
    confirmation_phrase = str(input_data.get("confirmation_phrase") or "").strip()

    if not recruiter_email:
        return {
            "agent": "agent_application_sender",
            "status": "no_recipient",
            "inputs_consumed": ["offer", "profile", "letter"],
            "outputs_produced": {
                "sent": False,
                "recipient": None,
            },
        }

    expected_phrase = str(settings.application_sender_confirmation_phrase or "JE CONFIRME L ENVOI").strip().upper()
    if (not user_confirmed) or (confirmation_phrase.upper() != expected_phrase):
        return {
            "agent": "agent_application_sender",
            "status": "confirmation_required",
            "inputs_consumed": ["offer", "profile", "letter"],
            "outputs_produced": {
                "sent": False,
                "recipient": recruiter_email,
                "required_confirmation_phrase": expected_phrase,
            },
        }

    subject, body = _build_letter_payload(offer, profile, provided_letter)

    if not _smtp_ready():
        return {
            "agent": "agent_application_sender",
            "status": "smtp_not_configured",
            "inputs_consumed": ["offer", "profile", "letter"],
            "outputs_produced": {
                "sent": False,
                "mode": "draft",
                "recipient": recruiter_email,
                "subject": subject,
                "body": body,
                "attachment_used": False,
            },
        }

    try:
        delivery = _send_email(recruiter_email, subject, body, user_id)
    except Exception as e:
        return {
            "agent": "agent_application_sender",
            "status": "send_error",
            "inputs_consumed": ["offer", "profile", "letter"],
            "outputs_produced": {
                "sent": False,
                "mode": "smtp",
                "recipient": recruiter_email,
                "subject": subject,
                "body": body,
                "attachment_used": False,
                "error": str(e),
            },
        }

    return {
        "agent": "agent_application_sender",
        "status": "sent",
        "inputs_consumed": ["offer", "profile", "letter"],
        "outputs_produced": {
            "sent": True,
            "mode": "smtp",
            "recipient": recruiter_email,
            "subject": subject,
            "body": body,
            "attachment_used": bool(delivery.get("attachment_used")),
        },
    }
