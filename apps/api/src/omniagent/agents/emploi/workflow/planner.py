"""JobWorkflowPlanner : transforme un intent emploi en Plan executable deterministe.

Le plan est un DAG : 7 steps, ordre topologique fixe. Meme input -> meme plan.

Branche avec le reste de l arch :
- Utilise Plan/PlanStep du core orchestrator
- Passe assert_deterministic_plan (Sprint 3+ determinism)
- S execute via l Orchestrator.run standard
"""
from __future__ import annotations
from typing import Any

from omniagent.core.orchestrator.planner.base import Plan, PlanStep, Planner
from omniagent.agents.emploi.workflow import JOB_PLAN_STEPS


class JobWorkflowPlanner(Planner):
    """Planner dedie au workflow Emploi (Vague A : squelette)."""

    PLAN_NAME = "job_workflow"
    PLAN_VERSION = "1.0.0"
    INTENT = "job_workflow_run"

    def supports(self, intent: str) -> bool:
        return intent == self.INTENT

    def build(self, intent: str, context: dict) -> Plan:
        steps: list[PlanStep] = []
        for spec in JOB_PLAN_STEPS:
            steps.append(PlanStep(
                agent_name=spec["agent_name"],
                depends_on=list(spec.get("depends_on", [])),
                input_template=self._input_template_for(spec["agent_name"], context),
                description=spec.get("description", ""),
            ))
        return Plan(name=self.PLAN_NAME, version=self.PLAN_VERSION, steps=steps)

    @staticmethod
    def _input_template_for(agent_name: str, context: dict) -> dict:
        """Template d input par agent (le context user est injecte par l orchestrateur)."""
        # L orchestrateur injecte {"step": input_template, "context": context} au runner.
        # On prepare le template pour que le runner resolve les cles automatiquement.
        if agent_name == "job_discovery":
            return {
                "sources": context.get("sources", ["france_travail"]),
                "query": context.get("query", ""),
                "location": context.get("location", ""),
                "max_results": context.get("max_results", 20),
            }
        if agent_name == "job_filter":
            return {
                "max_hours": context.get("max_hours", 168),
                "city": context.get("city"),
                "domain": context.get("domain", ""),
                "limit": context.get("limit", 20),
            }
        if agent_name in ("enrichment", "cv_matching", "cv_generator", "template_selector"):
            return {}
        if agent_name == "application":
            return {
                "dry_run": context.get("dry_run", True),
            }
        return {}


# Singleton pour registration dans le planner_registry.
job_workflow_planner = JobWorkflowPlanner()