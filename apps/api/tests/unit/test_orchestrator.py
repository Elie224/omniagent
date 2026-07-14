"""Tests du router d''intention et du planner."""
import pytest
from omniagent.core.orchestrator.router import IntentRouter, Intent
from omniagent.core.orchestrator.planner import Planner  # noqa: F401  (symbole reel : voir TemplatePlanner)
from omniagent.core.orchestrator.planner.base import TemplatePlanner


def test_intent_router_emploi():
    r = IntentRouter()
    assert r.route("Trouve moi une alternance data sur Paris") == Intent.SEARCH_JOB_AND_APPLY


def test_intent_router_recouvrement_removed_vague_b():
    """Vague B : le recouvrement a ete retire. Le router renvoie maintenant UNKNOWN
    pour les messages lies au recouvrement (pas de module actif)."""
    from omniagent.core.orchestrator.router import IntentRouter
    r = IntentRouter()
    assert r.route("Relance mes clients qui ont pas paye sur whatsapp") == Intent.UNKNOWN


def test_intent_router_marketing_removed_vague_b():
    """Vague B : le marketing a ete retire. Le router renvoie UNKNOWN."""
    from omniagent.core.orchestrator.router import IntentRouter
    r = IntentRouter()
    assert r.route("Prepare une semaine de contenu insta pour mon saas") == Intent.UNKNOWN


def test_planner_builds_plan():
    # Planner est abstrait (strategy pattern) : on utilise TemplatePlanner,
    # l implementation concrete qui couvre les intents connus.
    p = TemplatePlanner()
    plan = p.build("search_job_and_apply", {})
    agents = [s.agent_name for s in plan.steps]
    assert "agent_adzuna" in agents
    assert "agent_france_travail" in agents
    assert "agent_cv" in agents
    assert "agent_lettre" in agents