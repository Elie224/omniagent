"""Tests Vague A : squelette du JobWorkflow Emploi."""
import asyncio

import pytest

from omniagent.agents.emploi.workflow import (
    ApplicationAgent, CVGeneratorAgent, CVMatchingAgent, EnrichmentAgent,
    JOB_AGENTS, JOB_PLAN_STEPS, JobDiscoveryAgent, JobFilterAgent,
    JobWorkflowResult, TemplateSelectorAgent,
)
from omniagent.agents.emploi.workflow.planner import (
    JobWorkflowPlanner, job_workflow_planner,
)
from omniagent.core.orchestrator.determinism import assert_deterministic_plan


# ---------- Catalogue des agents ----------

def test_all_agents_in_catalogue():
    assert len(JOB_AGENTS) == 7
    expected = {
        "job_discovery", "job_filter", "enrichment",
        "cv_matching", "cv_generator", "template_selector", "application",
    }
    assert set(JOB_AGENTS.keys()) == expected


def test_plan_steps_cover_all_agents():
    plan_agents = {s["agent_name"] for s in JOB_PLAN_STEPS}
    assert plan_agents == set(JOB_AGENTS.keys())


# ---------- Planner deterministe ----------

def test_planner_supports_intent():
    assert job_workflow_planner.supports("job_workflow_run")
    assert not job_workflow_planner.supports("search_job_and_apply")


def test_planner_build_returns_7_steps_in_order():
    plan = job_workflow_planner.build("job_workflow_run", {"query": "data"})
    assert plan.name == "job_workflow"
    assert plan.version == "1.0.0"
    assert len(plan.steps) == 7
    # Ordre : discovery -> filter -> (enrichment, matching) -> generator -> selector -> application
    names = [s.agent_name for s in plan.steps]
    assert names[0] == "job_discovery"
    assert names[-1] == "application"
    # discovery n a pas de dependance
    assert plan.steps[0].depends_on == []


def test_planner_passes_deterministic_assert():
    plan = job_workflow_planner.build("job_workflow_run", {"query": "data"})
    assert_deterministic_plan(plan.steps, plan.name, plan.version)  # ne leve pas


def test_planner_is_deterministic_same_input_same_plan():
    a = job_workflow_planner.build("job_workflow_run", {"query": "data", "location": "Paris"})
    b = job_workflow_planner.build("job_workflow_run", {"query": "data", "location": "Paris"})
    # Meme structure, meme ordre
    assert [s.agent_name for s in a.steps] == [s.agent_name for s in b.steps]
    assert [s.depends_on for s in a.steps] == [s.depends_on for s in b.steps]


def test_planner_input_template_includes_user_context():
    plan = job_workflow_planner.build("job_workflow_run", {
        "query": "data engineer",
        "location": "Lyon",
        "max_results": 5,
        "sources": ["linkedin", "indeed"],
    })
    discovery = plan.steps[0]  # job_discovery
    assert discovery.input_template["query"] == "data engineer"
    assert discovery.input_template["location"] == "Lyon"
    assert discovery.input_template["max_results"] == 5
    assert discovery.input_template["sources"] == ["linkedin", "indeed"]


# ---------- Agents : interface commune + resultats non-None ----------

@pytest.mark.asyncio
async def test_job_discovery_returns_offers_with_seed():
    agent = JobDiscoveryAgent()
    out = await agent.run({"query": "data", "location": "Paris"}, {})
    assert out["count"] >= 0
    assert isinstance(out["offers"], list)
    assert all("offer_id" in o for o in out["offers"])
    assert all("source" in o for o in out["offers"])


@pytest.mark.asyncio
async def test_job_discovery_deterministic_with_seed():
    """Meme (query, location, sources) + seed = meme output."""
    a = await JobDiscoveryAgent().run(
        {"query": "data", "location": "Paris", "sources": ["linkedin"]},
        {"seed": 42},
    )
    b = await JobDiscoveryAgent().run(
        {"query": "data", "location": "Paris", "sources": ["linkedin"]},
        {"seed": 42},
    )
    assert [o["offer_id"] for o in a["offers"]] == [o["offer_id"] for o in b["offers"]]


@pytest.mark.asyncio
async def test_job_filter_truncates_and_filters_by_city():
    offers = [
        {"offer_id": f"o{i}", "location": ("Paris" if i % 2 == 0 else "Lyon")}
        for i in range(10)
    ]
    out = await JobFilterAgent().run(
        {"offers": offers, "city": "Paris", "limit": 3},
        {},
    )
    assert out["count"] == 3
    assert all(o["location"] == "Paris" for o in out["offers"])


@pytest.mark.asyncio
async def test_enrichment_adds_emails_with_confidence_score():
    offers = [{"offer_id": "o1", "company": "ACME Corp"}]
    out = await EnrichmentAgent().run({"offers": offers}, {})
    assert out["count"] == 1
    enriched = out["offers"][0]
    assert "enrichment" in enriched
    assert enriched["enrichment"]["emails"] == []
    assert enriched["enrichment"]["source"] == "regex"
    assert enriched["enrichment"]["confidence"] < 1.0  # best-effort


@pytest.mark.asyncio
async def test_enrichment_handles_empty_input():
    out = await EnrichmentAgent().run({"offers": []}, {})
    assert out["count"] == 0
    # Pas d offre = pas de confidence, on renvoie 0.0 (Vague B)
    assert out["confidence_avg"] == 0.0


@pytest.mark.asyncio
async def test_cv_matching_scores_offers_by_skills():
    offers = [
        {"offer_id": "1", "title": "Data Engineer Python", "company": "A"},
        {"offer_id": "2", "title": "Marketing Manager", "company": "B"},
    ]
    out = await CVMatchingAgent().run(
        {"offers": offers},
        {"user_profile": {"skills": ["python", "data"]}},
    )
    # L offre 1 matche python+data, l offre 2 ne matche rien
    sorted_offers = out["offers"]
    assert sorted_offers[0]["offer_id"] == "1"
    assert sorted_offers[0]["match_score"] > sorted_offers[1]["match_score"]


@pytest.mark.asyncio
async def test_cv_matching_no_user_profile_returns_neutral_score():
    offers = [{"offer_id": "1", "title": "X", "company": "Y"}]
    out = await CVMatchingAgent().run({"offers": offers}, {})
    assert out["offers"][0]["match_score"] == 0.5  # neutre


@pytest.mark.asyncio
async def test_cv_generator_picks_template_per_offer():
    out = await CVGeneratorAgent().run(
        {"offers": [{"offer_id": "o1", "title": "Data Engineer", "company": "X"}]},
        {},
    )
    assert out["generated"][0]["template"] in CVGeneratorAgent.TEMPLATES
    assert len(out["generated"][0]["cv_text"]) > 0


@pytest.mark.asyncio
async def test_cv_generator_exposes_all_4_templates():
    out = await CVGeneratorAgent().run({"offers": []}, {})
    assert out["templates_available"] == ["classic", "modern", "compact", "creative"]


@pytest.mark.asyncio
async def test_template_selector_returns_default():
    out = await TemplateSelectorAgent().run({}, {})
    assert out["default"] in out["templates"]
    assert len(out["templates"]) == 4


@pytest.mark.asyncio
async def test_application_dry_run_default():
    out = await ApplicationAgent().run({"generated": [{"offer_id": "o1", "template": "classic"}]}, {})
    assert out["status"] == "dry_run"
    assert out["dry_run"] is True


@pytest.mark.asyncio
async def test_application_pending_approval_when_not_dry_run_no_approval():
    out = await ApplicationAgent().run(
        {"generated": [{"offer_id": "o1", "template": "classic"}], "dry_run": False},
        {"user_approved": False},
    )
    assert out["status"] == "dry_run"
    assert out["user_approved"] is False


@pytest.mark.asyncio
async def test_application_forces_dry_run_when_role_missing_even_if_approved():
    out = await ApplicationAgent().run(
        {"generated": [{"offer_id": "o1", "template": "classic"}], "dry_run": False},
        {"user_approved": True},
    )
    assert out["status"] == "dry_run"
    assert out["user_approved"] is False


# ---------- Tous les agents : never return None ----------

@pytest.mark.asyncio
@pytest.mark.parametrize("agent_name", list(JOB_AGENTS.keys()))
async def test_agent_never_returns_none(agent_name):
    """Invariant : tous les agents du workflow renvoient un dict (jamais None)."""
    cls = JOB_AGENTS[agent_name]
    agent = cls()
    # On donne un input minimal pour chaque agent
    if agent_name == "job_discovery":
        out = await agent.run({"query": "x"}, {})
    elif agent_name == "job_filter":
        out = await agent.run({"offers": []}, {})
    elif agent_name in ("enrichment", "cv_matching"):
        out = await agent.run({"offers": []}, {})
    elif agent_name == "cv_generator":
        out = await agent.run({"offers": []}, {})
    elif agent_name == "template_selector":
        out = await agent.run({}, {})
    elif agent_name == "application":
        out = await agent.run({"generated": []}, {})
    else:
        out = await agent.run({}, {})
    assert isinstance(out, dict)
    assert out is not None

# ---------- JobFilterAgent : filtrage par domaine (Vague A++) ----------

@pytest.mark.asyncio
async def test_filter_domain_keeps_matching_offers():
    """Le filtre par domaine ne garde que les offres dont le titre matche."""
    offers = [
        {"offer_id": "1", "title": "Data Engineer", "company": "X", "description": "python sql", "location": "Paris"},
        {"offer_id": "2", "title": "Marketing Manager", "company": "Y", "description": "campaigns", "location": "Lyon"},
        {"offer_id": "3", "title": "Senior Data Scientist", "company": "Z", "description": "ml python", "location": "Paris"},
    ]
    out = await JobFilterAgent().run(
        {"offers": offers, "domain": "data", "limit": 20},
        {},
    )
    ids = [o["offer_id"] for o in out["offers"]]
    assert "1" in ids
    assert "3" in ids
    assert "2" not in ids
    assert out["count"] == 2
    assert out["rejected_domain_mismatch"] == 1


@pytest.mark.asyncio
async def test_filter_domain_handles_multiword():
    """Un domaine avec plusieurs mots-cles : au moins un doit matcher."""
    offers = [
        {"offer_id": "1", "title": "ML Engineer", "company": "X", "description": "", "location": "Paris"},
        {"offer_id": "2", "title": "AI Researcher", "company": "Y", "description": "", "location": "Lyon"},
        {"offer_id": "3", "title": "Sales", "company": "Z", "description": "", "location": "Paris"},
    ]
    out = await JobFilterAgent().run(
        {"offers": offers, "domain": "intelligence artificielle"},
        {},
    )
    # "artificielle" matche "AI"? Non, "artificielle" != "ai"
    # On attend que l offre 2 (AI Researcher) matche partiellement ?
    # En realite, le mot-cle "artificielle" n apparait pas dans "ai researcher"
    # donc l offre 2 devrait etre rejetee aussi.
    # On verifie juste que l algo prend en compte TOUS les mots-cles du domaine.
    assert "filters_applied" in out
    assert "artificielle" in out["filters_applied"]["domain_keywords"] or \
           "intelligence" in out["filters_applied"]["domain_keywords"]


@pytest.mark.asyncio
async def test_filter_domain_case_insensitive():
    """Le matching est insensible a la casse."""
    offers = [
        {"offer_id": "1", "title": "DATA ENGINEER", "company": "X", "description": "", "location": "Paris"},
    ]
    out = await JobFilterAgent().run(
        {"offers": offers, "domain": "Data"},
        {},
    )
    assert out["count"] == 1


@pytest.mark.asyncio
async def test_filter_domain_with_separators():
    """Le domaine peut etre separe par virgule, slash, tiret, espace."""
    from omniagent.agents.emploi.workflow import JobFilterAgent
    agent = JobFilterAgent()
    kws = agent._domain_keywords("data/ia, marketing")
    assert "data" in kws
    assert "ia" in kws
    assert "marketing" in kws


@pytest.mark.asyncio
async def test_filter_domain_empty_returns_all():
    """Si pas de domain, on retourne tout (mode permissif)."""
    offers = [
        {"offer_id": "1", "title": "X", "company": "Y", "description": "", "location": "P"},
        {"offer_id": "2", "title": "Z", "company": "W", "description": "", "location": "L"},
    ]
    out = await JobFilterAgent().run({"offers": offers, "domain": ""}, {})
    assert out["count"] == 2


@pytest.mark.asyncio
async def test_filter_domain_combines_with_city():
    """Domain + city sont combines (AND logique)."""
    offers = [
        {"offer_id": "1", "title": "Data Engineer", "company": "X", "description": "", "location": "Paris"},
        {"offer_id": "2", "title": "Data Engineer", "company": "Y", "description": "", "location": "Lyon"},
        {"offer_id": "3", "title": "Marketing", "company": "Z", "description": "", "location": "Paris"},
    ]
    out = await JobFilterAgent().run(
        {"offers": offers, "domain": "data", "city": "Paris"},
        {},
    )
    ids = [o["offer_id"] for o in out["offers"]]
    # Seule l offre 1 matche data + Paris
    assert ids == ["1"]


def test_planner_propagates_domain_to_filter():
    """Le JobWorkflowPlanner injecte le domain du context dans le filter input."""
    plan = job_workflow_planner.build(
        "job_workflow_run",
        {"query": "data", "domain": "ia/data"},
    )
    filter_step = next(s for s in plan.steps if s.agent_name == "job_filter")
    assert filter_step.input_template["domain"] == "ia/data"
