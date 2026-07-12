"""Enregistre les agents dans le registre au demarrage.

Vague B : focus Emploi uniquement.
  - 6 agents metier Emploi (coordinateur + 3 plateformes + CV + lettre)
  - 5 agents transverses (memory, knowledge, monitoring, planning, notification)
  - + JobWorkflowPlanner (plan Emploi dedie, Vague B)
"""
from omniagent.core.registry.agent_registry import AgentSpec, registry
from omniagent.agents.emploi.subagents.coordinator import run as run_emploi
from omniagent.agents.emploi.subagents.linkedin_agent import run as run_linkedin
from omniagent.agents.emploi.subagents.indeed_agent import run as run_indeed
from omniagent.agents.emploi.subagents.hellowork_agent import run as run_hellowork
from omniagent.agents.emploi.subagents.adzuna_agent import run as run_adzuna
from omniagent.agents.emploi.subagents.france_travail_agent import run as run_france_travail
from omniagent.agents.emploi.subagents.wttj_agent import run as run_wttj
from omniagent.agents.emploi.subagents.apec_agent import run as run_apec
from omniagent.agents.emploi.subagents.themuse_agent import run as run_themuse
from omniagent.agents.emploi.subagents.cv_agent import run as run_cv
from omniagent.agents.emploi.subagents.lettre_agent import run as run_lettre
from omniagent.agents.transverse.subagents.memory_agent import run as run_memory
from omniagent.agents.transverse.subagents.knowledge_agent import run as run_knowledge
from omniagent.agents.transverse.subagents.monitoring_agent import run as run_monitoring
from omniagent.agents.transverse.subagents.planning_agent import run as run_planning
from omniagent.agents.transverse.subagents.notification_agent import run as run_notification


def register_all_agents() -> None:
    """A appeler au demarrage de l''app."""
    specs = [
        # ---- Module Emploi (6) ----
        AgentSpec("agent_emploi", "emploi", "coordinateur",
                  "Coordonne la recherche d''emploi", run_emploi, dependencies=[]),
        AgentSpec("agent_linkedin", "emploi", "specialiste",
                  "Recherche d''offres LinkedIn", run_linkedin,
                  dependencies=["agent_emploi"]),
        AgentSpec("agent_indeed", "emploi", "specialiste",
                  "Recherche d''offres Indeed", run_indeed,
                  dependencies=["agent_emploi"]),
        AgentSpec("agent_hellowork", "emploi", "specialiste",
                  "Recherche d''offres HelloWork", run_hellowork,
                  dependencies=["agent_emploi"]),
        AgentSpec("agent_adzuna", "emploi", "specialiste",
                  "Agregateur Adzuna (FR+UK+US)", run_adzuna,
                  dependencies=["agent_emploi"]),
        AgentSpec("agent_france_travail", "emploi", "specialiste",
                  "France Travail (ex Pole Emploi) - API officielle", run_france_travail,
                  dependencies=["agent_emploi"]),
        AgentSpec("agent_wttj", "emploi", "specialiste",
                  "Welcome to the Jungle (startups FR)", run_wttj,
                  dependencies=["agent_emploi"]),
        AgentSpec("agent_apec", "emploi", "specialiste",
                  "APEC (cadres FR) - API officielle", run_apec,
                  dependencies=["agent_emploi"]),
        AgentSpec("agent_themuse", "emploi", "specialiste",
                  "The Muse (US/global tech)", run_themuse,
                  dependencies=["agent_emploi"]),
        AgentSpec("agent_cv", "emploi", "specialiste",
                  "Generation / adaptation CV", run_cv,
                  dependencies=["agent_linkedin", "agent_indeed", "agent_hellowork"]),
        AgentSpec("agent_lettre", "emploi", "specialiste",
                  "Generation lettre de motivation", run_lettre,
                  dependencies=["agent_cv"]),

        # ---- Agents transverses (5) ----
        AgentSpec("agent_memory", "transverse", "specialiste",
                  "Memoire utilisateur + vectorielle", run_memory, dependencies=[]),
        AgentSpec("agent_knowledge", "transverse", "specialiste",
                  "Recherche dans les documents", run_knowledge, dependencies=["agent_memory"]),
        AgentSpec("agent_monitoring", "transverse", "specialiste",
                  "Surveillance erreurs + reprises", run_monitoring, dependencies=[]),
        AgentSpec("agent_planning", "transverse", "specialiste",
                  "Planification des taches futures", run_planning, dependencies=[]),
        AgentSpec("agent_notification", "transverse", "specialiste",
                  "Notifications multi-canal", run_notification, dependencies=[]),
    ]
    for s in specs:
        registry.register(s)
    # Plan Emploi dedie (Vague B) : expose le workflow multi-agents du module Emploi
    _register_job_workflow_planner()


# --- Job workflow (Vague B) ---
def _register_job_workflow_planner() -> None:
    from omniagent.agents.emploi.workflow.planner import job_workflow_planner
    from omniagent.core.orchestrator.planner import planner_registry
    planner_registry.register(job_workflow_planner)