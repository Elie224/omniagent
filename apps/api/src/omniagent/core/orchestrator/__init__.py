"""Orchestrateur (canonique).

Arborescence :
    core/orchestrator/
        orchestrator.py     # Orchestrator (point d entree)
        router/             # IntentRouter (Rule + LLM + Fallback)
        planner/            # Planner strategy (Template / LLM)
        policies/           # ExecutionPolicy (Sequential / Parallel / Adaptive)
        graph/              # Variante LangGraph (optionnelle)

Le point d entree recommande est `Orchestrator` (et son singleton `orchestrator`).
"""
from omniagent.core.orchestrator.orchestrator import (
    Orchestrator,
    OrchestratorResult,
    orchestrator,
    orchestrator_v3,  # alias historique
)
from omniagent.core.orchestrator.router import Intent, IntentRouter, intent_router
from omniagent.core.orchestrator.planner import (
    Plan, PlanStep, Planner, PlannerRegistry,
    TemplatePlanner, LLMPoweredPlanner, planner_registry,
)
from omniagent.core.orchestrator.policies import (
    ExecutionPolicy, SequentialPolicy, ParallelPolicy, AdaptivePolicy, default_policy,
)

__all__ = [
    "Orchestrator", "OrchestratorResult", "orchestrator", "orchestrator_v3",
    "Intent", "IntentRouter", "intent_router",
    "Plan", "PlanStep", "Planner", "PlannerRegistry",
    "TemplatePlanner", "LLMPoweredPlanner", "planner_registry",
    "ExecutionPolicy", "SequentialPolicy", "ParallelPolicy", "AdaptivePolicy",
    "default_policy",
]
