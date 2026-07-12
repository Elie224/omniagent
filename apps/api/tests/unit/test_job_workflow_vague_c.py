"""Tests Vague C : CV matching semantique + ApplicationAgent envoi reel + RBAC."""
import pytest

from omniagent.agents.emploi.workflow import ApplicationAgent, CVMatchingAgent


# ---------- 2. CVMatchingAgent : scoring semantique ----------

@pytest.mark.asyncio
async def test_cv_matching_uses_cosine_not_keyword_overlap():
    """Le matching semantique detecte les synonymes la ou le keyword overlap echoue."""
    offers = [
        {"offer_id": "1", "title": "Machine Learning Engineer", "company": "ACME",
         "description": "We need an ML specialist with python and statistics skills.",
         "location": "Paris"},
    ]
    out = await CVMatchingAgent().run(
        {"offers": offers},
        {"user_profile": {
            "skills": ["python", "ml", "statistiques"],
            "previous_roles": ["data scientist"],
        }},
    )
    # Le score semantique doit etre > 0 (vocab commun : python, statistics)
    assert out["offers"][0]["match_score"] > 0.0


@pytest.mark.asyncio
async def test_cv_matching_zero_score_no_overlap():
    """Aucune intersection de vocabulaire -> score 0."""
    offers = [{"offer_id": "1", "title": "Marketing Specialist",
                "company": "X", "description": "campaigns social media",
                "location": "Lyon"}]
    out = await CVMatchingAgent().run(
        {"offers": offers},
        {"user_profile": {"skills": ["rust", "kubernetes"], "previous_roles": []}},
    )
    assert out["offers"][0]["match_score"] == 0.0


@pytest.mark.asyncio
async def test_cv_matching_high_score_for_perfect_match():
    """Un profil tres aligne avec l offre doit avoir un score proche de 1."""
    offers = [{"offer_id": "1", "title": "Python Data Engineer",
                "company": "ACME",
                "description": "We need python sql data engineer ml specialist.",
                "location": "Paris"}]
    out = await CVMatchingAgent().run(
        {"offers": offers},
        {"user_profile": {
            "skills": ["python", "sql", "data", "engineer", "ml"],
            "previous_roles": ["data engineer"],
        }},
    )
    assert out["offers"][0]["match_score"] > 0.5


@pytest.mark.asyncio
async def test_cv_matching_deterministic():
    """Meme input -> meme score (pas d alea)."""
    offers = [{"offer_id": "1", "title": "Data Engineer", "company": "X",
                "description": "python sql", "location": "Paris"}]
    a = await CVMatchingAgent().run(
        {"offers": offers}, {"user_profile": {"skills": ["python", "data"]}},
    )
    b = await CVMatchingAgent().run(
        {"offers": offers}, {"user_profile": {"skills": ["python", "data"]}},
    )
    assert a["offers"][0]["match_score"] == b["offers"][0]["match_score"]


@pytest.mark.asyncio
async def test_cv_matching_breakdown_exposed():
    """Le match expose un breakdown (semantic + skill_hits)."""
    offers = [{"offer_id": "1", "title": "Python Data Engineer",
                "company": "X", "description": "", "location": "Paris"}]
    out = await CVMatchingAgent().run(
        {"offers": offers},
        {"user_profile": {"skills": ["python", "data"]}},
    )
    assert "match_breakdown" in out["offers"][0]
    assert "semantic" in out["offers"][0]["match_breakdown"]
    assert "skill_hits" in out["offers"][0]["match_breakdown"]


# ---------- 3. ApplicationAgent : envoi reel via connector ----------

@pytest.mark.asyncio
async def test_application_dry_run_does_not_send():
    out = await ApplicationAgent().run(
        {
            "generated": [{"offer_id": "o1", "template": "classic"}],
            "offers": [{"offer_id": "o1", "company": "ACME",
                         "enrichment": {"emails": ["jobs@acme.com"], "contacts": {"hr": None}}}],
            "dry_run": True,
        },
        {"user_approved": True, "user_role": "admin"},
    )
    assert out["status"] == "dry_run"
    # Pas de send_results en dry_run
    assert all(r.get("status") != "sent" for r in out["send_results"])


@pytest.mark.asyncio
async def test_application_sends_email_when_approved_and_rbac_ok():
    """Avec approved=True + role admin + dry_run=False, on envoie vraiment."""
    out = await ApplicationAgent().run(
        {
            "generated": [{"offer_id": "o1", "template": "modern"}],
            "offers": [{
                "offer_id": "o1", "title": "Data Engineer", "company": "ACME",
                "enrichment": {
                    "emails": ["jobs@acme.com"],
                    "contacts": {"hr": "rh@acme.com"},
                },
            }],
            "dry_run": False,
        },
        {"user_approved": True, "user_role": "admin"},
    )
    assert out["status"] == "sent"
    # Le send_results doit contenir un envoi
    assert len(out["send_results"]) == 1
    assert out["send_results"][0]["sent"] is True
    # Priorite : HR > 1er email
    assert out["send_results"][0]["to"] == "rh@acme.com"


@pytest.mark.asyncio
async def test_application_skips_when_no_contact_email():
    """Si aucun email de contact, on skip proprement (pas d envoi)."""
    out = await ApplicationAgent().run(
        {
            "generated": [{"offer_id": "o1", "template": "classic"}],
            "offers": [{"offer_id": "o1", "title": "X", "company": "Y",
                         "enrichment": {"emails": [], "contacts": {"hr": None}}}],
            "dry_run": False,
        },
        {"user_approved": True, "user_role": "admin"},
    )
    assert out["send_results"][0]["skipped"] is True
    assert "no_contact_email" in out["send_results"][0]["reason"]


# ---------- 4. ApplicationAgent : RBAC ----------

@pytest.mark.asyncio
async def test_application_rbac_blocks_non_authorized_user():
    """Un user non autorise ne peut PAS envoyer, meme si approved=True."""
    out = await ApplicationAgent().run(
        {
            "generated": [{"offer_id": "o1", "template": "classic"}],
            "offers": [{"offer_id": "o1", "title": "X", "company": "Y",
                         "enrichment": {"emails": ["hr@y.com"], "contacts": {"hr": "hr@y.com"}}}],
            "dry_run": False,
        },
        {"user_approved": True, "user_role": "user"},
    )
    # RBAC a force dry_run
    assert out["dry_run"] is True
    assert out["user_approved"] is False
    assert out["status"] == "dry_run"
    # Pas de send
    assert all(r.get("status") != "sent" for r in out["send_results"])


@pytest.mark.asyncio
async def test_application_rbac_admin_can_send():
    """Un admin peut envoyer."""
    out = await ApplicationAgent().run(
        {
            "generated": [{"offer_id": "o1", "template": "classic"}],
            "offers": [{"offer_id": "o1", "title": "X", "company": "Y",
                         "enrichment": {"emails": ["hr@y.com"], "contacts": {"hr": "hr@y.com"}}}],
            "dry_run": False,
        },
        {"user_approved": True, "user_role": "admin"},
    )
    assert out["dry_run"] is False
    assert out["user_approved"] is True
    assert out["status"] == "sent"


@pytest.mark.asyncio
async def test_application_rbac_recruiter_can_send():
    """Un recruiter peut envoyer."""
    out = await ApplicationAgent().run(
        {
            "generated": [{"offer_id": "o1", "template": "classic"}],
            "offers": [{"offer_id": "o1", "title": "X", "company": "Y",
                         "enrichment": {"emails": ["hr@y.com"], "contacts": {"hr": "hr@y.com"}}}],
            "dry_run": False,
        },
        {"user_approved": True, "user_role": "recruiter"},
    )
    assert out["status"] == "sent"


@pytest.mark.asyncio
async def test_application_rbac_dry_run_always_works():
    """Le dry_run marche pour tout le monde, meme sans RBAC (mode preview)."""
    out = await ApplicationAgent().run(
        {
            "generated": [{"offer_id": "o1", "template": "classic"}],
            "offers": [],
            "dry_run": True,
        },
        {"user_approved": True, "user_role": "user"},
    )
    assert out["status"] == "dry_run"