"""Variante LangGraph (optionnelle).

L orchestrateur canonique est `omniagent.core.orchestrator.orchestrator.Orchestrator`
(Strategy Planner + ExecutionPolicy). Cette variante montre comment l exprimer
en StateGraph LangGraph pour des cas ou le besoin de visual inspection est fort.

Non utilisee par defaut par main.py.
"""
from omniagent.core.orchestrator.graph.langgraph import (
    build_orchestrator_graph,
    OrchestratorState,
)

__all__ = ["build_orchestrator_graph", "OrchestratorState"]
