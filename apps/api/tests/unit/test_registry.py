"""Tests du registre d''agents (Vague B : focus Emploi).

16 agents : 11 metier Emploi + 5 transverses.
"""
import pytest
from omniagent.core.registry.agent_registry import AgentSpec, registry
from omniagent.agents.manager.registration import register_all_agents


@pytest.fixture(autouse=True)
def reset_registry():
    registry._agents.clear()
    yield


def test_all_16_agents_registered():
    """Vague B : 11 agents Emploi + 5 transverses = 16 agents (avec APEC et The Muse)."""
    register_all_agents()
    agents = registry.all()
    assert len(agents) == 16, f"Attendu 16, obtenu {len(agents)} : {[a.name for a in agents]}"
    names = {a.name for a in agents}
    expected = {
        # Emploi (11)
        "agent_emploi", "agent_linkedin", "agent_indeed", "agent_hellowork",
        "agent_adzuna", "agent_france_travail", "agent_wttj",
        "agent_apec", "agent_themuse",
        "agent_cv", "agent_lettre",
        # Transverse (5)
        "agent_memory", "agent_knowledge", "agent_monitoring",
        "agent_planning", "agent_notification",
    }
    assert names == expected


def test_agents_have_module_and_role():
    register_all_agents()
    for a in registry.all():
        # Vague B : modules possibles = emploi + transverse uniquement
        assert a.module in {"emploi", "transverse"}, f"Module inattendu: {a.module}"
        assert a.role in {"coordinateur", "specialiste"}


def test_transverse_agents_count():
    register_all_agents()
    transverse = registry.list_by_module("transverse")
    assert len(transverse) == 5


def test_emploi_agents_count():
    """Vague B : 11 agents dans le module Emploi (6 de base + 5 plateformes additionnelles)."""
    register_all_agents()
    emploi = registry.list_by_module("emploi")
    assert len(emploi) == 11
    names = {a.name for a in emploi}
    assert "agent_emploi" in names  # coordinateur