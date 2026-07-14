"""Enregistre les agents dans le registre au demarrage.

Vague B : focus Emploi uniquement.
    - Agents Emploi API-first (France Travail, Adzuna, The Muse)
    - 5 agents transverses (memory, knowledge, monitoring, planning, notification)
    - + JobWorkflowPlanner (plan Emploi dedie, Vague B)
"""
from omniagent.core.registry.agent_registry import AgentSpec, registry
from omniagent.agents.emploi.subagents.coordinator import run as run_emploi
from omniagent.agents.emploi.subagents.adzuna_agent import run as run_adzuna
from omniagent.agents.emploi.subagents.france_travail_agent import run as run_france_travail
from omniagent.agents.emploi.subagents.themuse_agent import run as run_themuse
from omniagent.agents.emploi.subagents.cv_agent import run as run_cv
from omniagent.agents.emploi.subagents.lettre_agent import run as run_lettre
from omniagent.agents.emploi.subagents.interview_coach_agent import run as run_interview_coach
from omniagent.agents.emploi.subagents.salary_benchmark_agent import run as run_salary_benchmark
from omniagent.agents.emploi.subagents.followup_agent import run as run_followup
from omniagent.agents.emploi.subagents.contact_enrichment_agent import run as run_contact_enrichment
from omniagent.agents.emploi.subagents.lettre_requirement_agent import run as run_lettre_requirement
from omniagent.agents.emploi.subagents.application_sender_agent import run as run_application_sender
from omniagent.agents.emploi.subagents.filtering_matching_agent import run as run_filtering_matching
from omniagent.agents.emploi.subagents.mission_controller_agent import run as run_mission_controller
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
        AgentSpec("agent_adzuna", "emploi", "specialiste",
                  "Agregateur Adzuna (FR+UK+US)", run_adzuna,
                  dependencies=["agent_emploi"]),
        AgentSpec("agent_france_travail", "emploi", "specialiste",
                  "France Travail (ex Pole Emploi) - API officielle", run_france_travail,
                  dependencies=["agent_emploi"]),
        AgentSpec("agent_themuse", "emploi", "specialiste",
                  "The Muse (US/global tech)", run_themuse,
                  dependencies=["agent_emploi"]),
        AgentSpec("agent_cv", "emploi", "specialiste",
                  "Generation / adaptation CV", run_cv,
                  dependencies=["agent_adzuna", "agent_france_travail"]),
        AgentSpec("agent_lettre", "emploi", "specialiste",
                  "Generation lettre de motivation", run_lettre,
                  dependencies=["agent_cv"]),

        AgentSpec("agent_interview_coach", "emploi", "specialiste",
                  "Preparation aux entretiens (questions, pitch, red flags)", run_interview_coach,
                  dependencies=["agent_emploi"]),
        AgentSpec("agent_salary_benchmark", "emploi", "specialiste",
                  "Benchmark salarial par role/ville/experience", run_salary_benchmark,
                  dependencies=["agent_emploi"]),
        AgentSpec("agent_followup", "emploi", "specialiste",
                  "Relance automatique des candidatures envoyees", run_followup,
                  dependencies=["agent_emploi"]),
        AgentSpec("agent_contact_enrichment", "emploi", "specialiste",
              "Recherche email/telephone publics entreprise pour une offre", run_contact_enrichment,
              dependencies=["agent_emploi"]),
        AgentSpec("agent_lettre_requirement", "emploi", "specialiste",
              "Genere la lettre de motivation seulement si demandee dans l'offre", run_lettre_requirement,
              dependencies=["agent_emploi"]),
          AgentSpec("agent_filtering_matching", "emploi", "specialiste",
              "Filtre les offres et calcule un score de compatibilite profil/offre", run_filtering_matching,
              dependencies=["agent_emploi"]),
          AgentSpec("agent_mission_controller", "emploi", "coordinateur",
              "Pilote la mission de bout en bout avec gestion des echecs partiels", run_mission_controller,
              dependencies=["agent_emploi", "agent_filtering_matching", "agent_contact_enrichment", "agent_lettre_requirement", "agent_application_sender"]),
          AgentSpec("agent_application_sender", "emploi", "specialiste",
              "Envoie la candidature par email au recruteur", run_application_sender,
              dependencies=["agent_emploi"]),

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
