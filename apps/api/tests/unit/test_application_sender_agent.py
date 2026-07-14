import types

import pytest

from omniagent.agents.emploi.subagents import application_sender_agent as sender


@pytest.mark.asyncio
async def test_application_sender_no_recipient():
    out = await sender.run({"offer": {"title": "Data Scientist"}}, user_id="u1")
    assert out["status"] == "no_recipient"
    assert out["outputs_produced"]["sent"] is False


@pytest.mark.asyncio
async def test_application_sender_sends_with_smtp(monkeypatch):
    monkeypatch.setattr(sender.settings, "smtp_host", "smtp.test.local")
    monkeypatch.setattr(sender.settings, "smtp_port", 587)
    monkeypatch.setattr(sender.settings, "smtp_use_tls", True)
    monkeypatch.setattr(sender.settings, "smtp_username", "user")
    monkeypatch.setattr(sender.settings, "smtp_password", "pass")
    monkeypatch.setattr(sender.settings, "smtp_from_email", "bot@example.com")
    monkeypatch.setattr(sender.settings, "smtp_from_name", "OmniAgent")
    monkeypatch.setattr(sender.settings, "application_sender_require_cv", False)
    monkeypatch.setattr(sender.settings, "application_sender_confirmation_phrase", "JE CONFIRME L ENVOI")

    class _SMTP:
        def __init__(self, host, port, timeout):
            self.host = host
            self.port = port
            self.timeout = timeout
            self.sent = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self):
            return None

        def login(self, username, password):
            assert username == "user"
            assert password == "pass"

        def send_message(self, msg):
            assert msg["To"] == "rh@example.com"
            self.sent = True

    monkeypatch.setattr(sender.smtplib, "SMTP", _SMTP)
    monkeypatch.setattr(sender, "_resolve_generated_cv_path", lambda uid: __import__("pathlib").Path("__missing__.pdf"))

    out = await sender.run(
        {
            "offer": {"title": "Data Scientist", "company": "ACME"},
            "recruiter_email": "rh@example.com",
            "letter": {"subject": "Sujet", "body": "Bonjour"},
            "profile": {"full_name": "Alice"},
            "user_confirmed": True,
            "confirmation_phrase": "JE CONFIRME L ENVOI",
        },
        user_id="u1",
    )

    assert out["status"] == "sent"
    assert out["outputs_produced"]["sent"] is True
    assert out["outputs_produced"]["recipient"] == "rh@example.com"


@pytest.mark.asyncio
async def test_application_sender_requires_explicit_confirmation(monkeypatch):
    monkeypatch.setattr(sender.settings, "application_sender_confirmation_phrase", "JE CONFIRME L ENVOI")
    out = await sender.run(
        {
            "offer": {"title": "Data Scientist", "company": "ACME"},
            "recruiter_email": "rh@example.com",
            "letter": {"subject": "Sujet", "body": "Bonjour"},
            "profile": {"full_name": "Alice"},
            "user_confirmed": False,
            "confirmation_phrase": "",
        },
        user_id="u1",
    )
    assert out["status"] == "confirmation_required"
    assert out["outputs_produced"]["sent"] is False
