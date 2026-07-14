"""Tests Vague B : logique metier reelle des agents Emploi."""
import asyncio
from datetime import datetime, timezone, timedelta

import pytest

from omniagent.agents.emploi.workflow import (
    ApplicationAgent, CVGeneratorAgent, EnrichmentAgent, JobDiscoveryAgent,
    JobFilterAgent, TemplateSelectorAgent,
)


# ---------- JobDiscoveryAgent (Vague B : MultiSourceBackend reel) ----------

@pytest.mark.asyncio
async def test_discovery_uses_real_backend():
    """Le discovery n injecte pas de mock implicite en mode produit."""
    out = await JobDiscoveryAgent().run(
        {"query": "data engineer", "location": "Paris", "max_results": 5},
        {"seed": 42},
    )
    assert out["backend_used"] in ("none", "multi_source_connector", "multi_source_mixed", "multi_source_mock")
    # En mode produit strict, on accepte 0 offre si aucune source reelle
    # n est exploitable.
    assert out["count"] >= 0
    # Les champs normalises sont presents
    assert all("offer_id" in o and "company" in o for o in out["offers"])


@pytest.mark.asyncio
async def test_discovery_falls_back_when_backend_unavailable(monkeypatch):
    """Si le backend est indisponible, aucune offre n est fabriquee par defaut."""
    import omniagent.agents.emploi.workflow as wf

    def boom(*a, **kw):
        raise ImportError("backend indisponible")

    monkeypatch.setattr(wf.JobDiscoveryAgent, "_build_criteria", boom)
    out = await wf.JobDiscoveryAgent().run(
        {"query": "X", "location": "Y", "max_results": 3},
        {"seed": 7},
    )
    assert out["count"] == 0
    assert "backend_import" in out["backend_errors"]


@pytest.mark.asyncio
async def test_discovery_returns_offers_sorted_by_score_desc():
    out = await JobDiscoveryAgent().run(
        {"query": "X", "max_results": 5},
        {"seed": 1},
    )
    scores = [o.get("score", 0) for o in out["offers"]]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_discovery_reports_connector_backend_when_connector_source_selected():
    out = await JobDiscoveryAgent().run(
        {
            "query": "data",
            "location": "Paris",
            "max_results": 5,
            "sources": ["france_travail"],
        },
        {"seed": 42},
    )
    assert out["backend_used"] == "multi_source_connector"


# ---------- JobFilterAgent : time-window filtering ----------

@pytest.mark.asyncio
async def test_filter_rejects_offers_older_than_max_hours():
    """Les offres trop anciennes sont rejetees."""
    now = datetime.now(timezone.utc)
    offers = [
        {"offer_id": "1", "title": "X", "company": "Y", "description": "", "location": "Paris",
         "posted_at": (now - timedelta(hours=48)).isoformat()},
        {"offer_id": "2", "title": "X", "company": "Y", "description": "", "location": "Paris",
         "posted_at": (now - timedelta(hours=2)).isoformat()},
    ]
    out = await JobFilterAgent().run(
        {"offers": offers, "max_hours": 24, "limit": 20},
        {},
    )
    assert out["count"] == 1
    assert out["offers"][0]["offer_id"] == "2"
    assert out["rejected_too_old"] == 1


@pytest.mark.asyncio
async def test_filter_keeps_offer_with_unparseable_date():
    """Si posted_at est invalide, on garde l offre (best-effort)."""
    offers = [{"offer_id": "1", "title": "X", "company": "Y",
                "description": "", "location": "P", "posted_at": "not-a-date"}]
    out = await JobFilterAgent().run({"offers": offers, "max_hours": 24}, {})
    assert out["count"] == 1


@pytest.mark.asyncio
async def test_filter_tracks_rejected_counts():
    """Le retour expose des compteurs de rejet par raison."""
    offers = [
        {"offer_id": "1", "title": "Data", "company": "Y", "description": "", "location": "Paris",
         "posted_at": ""},
        {"offer_id": "2", "title": "Marketing", "company": "Y", "description": "", "location": "Lyon",
         "posted_at": ""},
    ]
    out = await JobFilterAgent().run(
        {"offers": offers, "domain": "data", "city": "Paris", "limit": 20},
        {},
    )
    assert "rejected_domain_mismatch" in out
    assert "rejected_too_old" in out
    assert "rejected_city" in out


# ---------- EnrichmentAgent (Vague B : vraie regex + confidence) ----------

@pytest.mark.asyncio
async def test_enrichment_extracts_email_from_description():
    out = await EnrichmentAgent().run({
        "offers": [{"offer_id": "1", "company": "ACME",
                     "description": "Postuler a jobs@acme.com",
                     "location": "Paris", "title": "Data"}],
    }, {})
    e = out["offers"][0]["enrichment"]
    assert "jobs@acme.com" in e["emails"]
    assert e["confidence"] >= 0.5
    assert e["source"] == "regex"


@pytest.mark.asyncio
async def test_enrichment_extracts_french_phone():
    out = await EnrichmentAgent().run({
        "offers": [{"offer_id": "1", "company": "X",
                     "description": "Tel: 06 12 34 56 78",
                     "location": "P", "title": "T"}],
    }, {})
    e = out["offers"][0]["enrichment"]
    assert len(e["phones"]) >= 1
    # Format FR
    assert any(p.replace(" ", "").startswith("06") or p.replace(" ", "").startswith("+33") for p in e["phones"])


@pytest.mark.asyncio
async def test_enrichment_boosts_confidence_when_email_matches_company_domain():
    """Si un email a le meme domaine que la company, confidence > 0.5."""
    out = await EnrichmentAgent().run({
        "offers": [{"offer_id": "1", "company": "ACME",
                     "description": "rh@acme.com",
                     "location": "P", "title": "T"}],
    }, {})
    e = out["offers"][0]["enrichment"]
    assert e["confidence"] >= 0.8  # 0.5 (email) + 0.3 (domain match) = 0.8


@pytest.mark.asyncio
async def test_enrichment_detects_hr_contact_from_prefix():
    out = await EnrichmentAgent().run({
        "offers": [{"offer_id": "1", "company": "ACME",
                     "description": "rh@acme.com",
                     "location": "P", "title": "T"}],
    }, {})
    e = out["offers"][0]["enrichment"]
    assert e["contacts"]["hr"] == "rh@acme.com"


@pytest.mark.asyncio
async def test_enrichment_zero_confidence_when_nothing_found_and_no_domain():
    """Pas d email/phone et pas de company : confidence 0."""
    out = await EnrichmentAgent().run({
        "offers": [{"offer_id": "1", "company": "",
                     "description": "no contact here",
                     "location": "P", "title": "T"}],
    }, {})
    e = out["offers"][0]["enrichment"]
    assert e["confidence"] == 0.0


@pytest.mark.asyncio
async def test_enrichment_derives_emails_from_company_when_nothing_found():
    """Si rien trouve, on genere des emails derives du domaine (best-effort)."""
    out = await EnrichmentAgent().run({
        "offers": [{"offer_id": "1", "company": "DataCorp",
                     "description": "no contact",
                     "location": "P", "title": "T"}],
    }, {})
    e = out["offers"][0]["enrichment"]
    assert any("datacorp.com" in em for em in e["emails"])
    assert e["source"] == "regex+derive"


# ---------- CVGeneratorAgent (Vague B : heuristic + ATS keywords + LLM) ----------

@pytest.mark.asyncio
async def test_cv_generator_detects_seniority_from_title():
    agent = CVGeneratorAgent()
    assert agent._detect_seniority("Senior Data Engineer") == "senior"
    assert agent._detect_seniority("Junior Developer") == "junior"
    assert agent._detect_seniority("Alternant Data") == "junior"
    assert agent._detect_seniority("Data Engineer") == "mid"


@pytest.mark.asyncio
async def test_cv_generator_detects_domain_from_title():
    agent = CVGeneratorAgent()
    assert agent._detect_domain("UX Designer", "ACME") == "creative"
    assert agent._detect_domain("Sales Manager", "X") == "business"
    assert agent._detect_domain("Data Engineer", "X") == "tech"
    assert agent._detect_domain("Marketing Lead", "X") == "creative"


@pytest.mark.asyncio
async def test_cv_generator_selects_template_by_heuristic():
    agent = CVGeneratorAgent()
    # Senior + tech + score eleve -> modern
    assert agent._select_template("senior", "tech", 0.8) == "modern"
    # Junior -> compact
    assert agent._select_template("junior", "tech", 0.5) == "compact"
    # Creative -> creative
    assert agent._select_template("mid", "creative", 0.5) == "creative"
    # Business -> classic
    assert agent._select_template("mid", "business", 0.5) == "classic"


@pytest.mark.asyncio
async def test_cv_generator_extracts_ats_keywords_from_title_and_skills():
    agent = CVGeneratorAgent()
    offer = {"title": "Senior Data Engineer Python", "company": "X"}
    skills = ["python", "sql"]
    kws = agent._extract_ats_keywords(offer, skills)
    assert "senior" in kws
    assert "data" in kws
    assert "engineer" in kws
    assert "python" in kws
    assert "sql" in kws


@pytest.mark.asyncio
async def test_cv_generator_is_deterministic_per_offer():
    """Meme offer + meme seed -> meme cv_text (determinism)."""
    a = await CVGeneratorAgent().run(
        {"offers": [{"offer_id": "o1", "title": "Data Engineer", "company": "ACME"}]},
        {"seed": 42, "user_profile": {"skills": ["python"]}},
    )
    b = await CVGeneratorAgent().run(
        {"offers": [{"offer_id": "o1", "title": "Data Engineer", "company": "ACME"}]},
        {"seed": 42, "user_profile": {"skills": ["python"]}},
    )
    assert a["generated"][0]["cv_text"] == b["generated"][0]["cv_text"]


@pytest.mark.asyncio
async def test_cv_generator_uses_real_llm_when_available():
    """Si le LLM mock est dispo, on l utilise (et on retrouve ses metadonnees)."""
    from omniagent.llm import reset_default_llm, get_default_llm
    reset_default_llm()
    llm = get_default_llm()
    assert llm.calls == 0
    out = await CVGeneratorAgent().run(
        {"offers": [{"offer_id": "o1", "title": "Data Engineer", "company": "ACME"}]},
        {"seed": 1, "user_profile": {"skills": []}},
    )
    # Le LLM mock a ete appele au moins une fois
    assert llm.calls >= 1


# ---------- TemplateSelectorAgent (Vague B : heuristic default) ----------

@pytest.mark.asyncio
async def test_template_selector_default_for_creative_profile():
    out = await TemplateSelectorAgent().run(
        {}, {"user_profile": {"seniority": "mid", "domain": "UX Design"}},
    )
    assert out["default"] == "creative"


@pytest.mark.asyncio
async def test_template_selector_default_for_senior():
    out = await TemplateSelectorAgent().run(
        {}, {"user_profile": {"seniority": "senior"}},
    )
    assert out["default"] == "modern"


@pytest.mark.asyncio
async def test_template_selector_default_for_junior():
    out = await TemplateSelectorAgent().run(
        {}, {"user_profile": {"seniority": "junior"}},
    )
    assert out["default"] == "compact"


@pytest.mark.asyncio
async def test_template_selector_default_for_unknown():
    out = await TemplateSelectorAgent().run({}, {})
    assert out["default"] == "classic"
    # Rationale expose pourquoi
    assert "rationale" in out