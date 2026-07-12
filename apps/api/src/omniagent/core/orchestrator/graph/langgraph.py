"""Variante LangGraph de l orchestrateur (illustrative).

Le pipeline canonique reste `Orchestrator` (Strategy + Policy). Cette
implementation StateGraph peut etre utilisee pour debugger visuellement un
workflow ou pour integrer avec un executor LangGraph.
"""
from __future__ import annotations
from typing import TypedDict

from langgraph.graph import StateGraph, END

from omniagent.core.orchestrator.router import intent_router, Intent
from omniagent.core.orchestrator.planner import planner_registry
from omniagent.agents.manager.runner import agent_manager


class OrchestratorState(TypedDict, total=False):
    user_id: str
    user_message: str
    intent: str
    plan: list[str]
    results: dict[str, dict]
    final_output: dict


def route_node(state: OrchestratorState) -> OrchestratorState:
    """Identifie l intent (sync, sans LLM pour rester deterministe)."""
    intent = intent_router.route(state.get("user_message", ""))
    return {**state, "intent": intent.value}


def plan_node(state: OrchestratorState) -> OrchestratorState:
    """Construit la liste d etapes a partir du planner."""
    intent_value = state.get("intent", "")
    if not intent_value or intent_value == Intent.UNKNOWN.value:
        return {**state, "plan": []}
    planner = planner_registry.get_for(intent_value)
    plan = planner.build(intent_value, state.get("results") or {})
    return {**state, "plan": [s.agent_name for s in plan.steps]}


async def execute_node(state: OrchestratorState) -> OrchestratorState:
    """Execute les etapes en sequence (version simplifiee)."""
    results = {}
    user_id = state.get("user_id", "demo")
    for agent_name in state.get("plan", []):
        run = await agent_manager.run(
            agent_name, user_id,
            {"step": {}, "context": state.get("results") or {}},
        )
        results[agent_name] = {
            "status": run.status.value,
            "output": run.output,
            "error": run.error,
        }
        if run.status.value != "success":
            break
    return {**state, "results": results}


def build_orchestrator_graph():
    """Compile le StateGraph. Utilisable en debug ou en variante d execution."""
    g = StateGraph(OrchestratorState)
    g.add_node("route", route_node)
    g.add_node("plan", plan_node)
    g.add_node("execute", execute_node)
    g.set_entry_point("route")
    g.add_edge("route", "plan")
    g.add_edge("plan", "execute")
    g.add_edge("execute", END)
    return g.compile()
