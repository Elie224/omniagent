"""Interface Planner + implementations interchangeables (strategy pattern).

Vague B (focus Emploi) : seul le template search_job_and_apply est actif.
Les anciens templates send_reminder et marketing_week ont ete retires avec
les modules recouvrement et marketing.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class PlanStep:
    agent_name: str
    depends_on: list[str]
    input_template: dict
    description: str
    timeout_s: int = 300


@dataclass
class Plan:
    name: str
    version: str
    steps: list[PlanStep]

    def next_runnable(self, done: set[str]) -> list[PlanStep]:
        return [s for s in self.steps
                if s.agent_name not in done
                and all(d in done for d in s.depends_on)]


class Planner(ABC):
    """Strategy : un planner transforme (intent, context) en Plan executable."""

    @abstractmethod
    def supports(self, intent: str) -> bool: ...

    @abstractmethod
    def build(self, intent: str, context: dict) -> Plan: ...


class TemplatePlanner(Planner):
    """Planner base sur des templates statiques."""

    def __init__(self):
        self._templates: dict[str, list[PlanStep]] = {
            "search_job_and_apply": [
                PlanStep("agent_emploi", [], {}, "Coordonner la recherche"),
                PlanStep("agent_linkedin",  ["agent_emploi"], {"criteria": "user.criteria"}, "Recherche LinkedIn"),
                PlanStep("agent_indeed",    ["agent_emploi"], {"criteria": "user.criteria"}, "Recherche Indeed"),
                PlanStep("agent_hellowork", ["agent_emploi"], {"criteria": "user.criteria"}, "Recherche HelloWork"),
                PlanStep("agent_adzuna",         ["agent_emploi"], {"criteria": "user.criteria"}, "Recherche Adzuna"),
                PlanStep("agent_france_travail", ["agent_emploi"], {"criteria": "user.criteria"}, "Recherche France Travail"),
                PlanStep("agent_wttj",           ["agent_emploi"], {"criteria": "user.criteria"}, "Recherche Welcome to the Jungle"),
                PlanStep("agent_apec",            ["agent_emploi"], {"criteria": "user.criteria"}, "Recherche APEC"),
                PlanStep("agent_themuse",         ["agent_emploi"], {"criteria": "user.criteria"}, "Recherche The Muse"),
                PlanStep("agent_cv",        ["agent_linkedin", "agent_indeed", "agent_hellowork",
                                              "agent_adzuna", "agent_france_travail", "agent_wttj",
                                              "agent_apec", "agent_themuse"],
                         {"offer_id": "selected_offer"}, "Adapter le CV"),
                PlanStep("agent_lettre",    ["agent_cv"], {"offer_id": "selected_offer"}, "Rediger la lettre"),
            ],
        }

    def supports(self, intent: str) -> bool:
        return intent in self._templates

    def build(self, intent: str, context: dict) -> Plan:
        steps = self._templates.get(intent, [])
        return Plan(name=intent, version="1.0.0", steps=steps)


class LLMPoweredPlanner(Planner):
    """Planner dynamique : genere le plan via un LLM a partir du contexte.

    Plus lent que TemplatePlanner mais peut gerer des intents nouveaux.
    """

    def __init__(self, fallback: Planner, llm_call):
        self._fallback = fallback
        self._llm_call = llm_call

    def supports(self, intent: str) -> bool:
        return True  # supporte tout (avec fallback)

    def build(self, intent: str, context: dict) -> Plan:
        if self._fallback.supports(intent):
            return self._fallback.build(intent, context)
        # Sinon : appel LLM pour generer un plan
        try:
            plan = self._llm_call(intent, context)
            return plan
        except Exception:
            return Plan(name=intent, version="1.0.0", steps=[])

class PlannerRegistry:
    """Registre des planners : plusieurs strategies coexistent (TemplatePlanner, LLMPoweredPlanner)."""

    def __init__(self):
        self._planners: list[Planner] = []

    def register(self, planner: Planner) -> None:
        self._planners.append(planner)

    def supports(self, intent: str) -> bool:
        return any(p.supports(intent) for p in self._planners)

    def get_for(self, intent: str) -> Planner:
        """Retourne le premier planner qui supporte l intent, ou un planner vide."""
        for p in self._planners:
            if p.supports(intent):
                return p
        # Fallback : un planner qui retourne toujours un plan vide
        class _EmptyPlanner(Planner):
            def supports(self, intent: str) -> bool:
                return True
            def build(self, intent: str, context: dict) -> Plan:
                return Plan(name=intent, version="0.0.0", steps=[])
        return _EmptyPlanner()

    def build(self, intent: str, context: dict) -> Plan:
        for p in self._planners:
            if p.supports(intent):
                return p.build(intent, context)
        return Plan(name=intent, version="0.0.0", steps=[])


planner_registry = PlannerRegistry()
planner_registry.register(TemplatePlanner())
