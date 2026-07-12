"""Orchestrateur (canonique).

Compose Planner + Policy + IntentRouter + AgentManager.
Le seul point d entree pour executer un plan multi-agents.
"""
from __future__ import annotations
from dataclasses import dataclass

from omniagent.core.orchestrator.planner import planner_registry
from omniagent.core.orchestrator.policies import default_policy, ExecutionPolicy
from omniagent.core.orchestrator.router import intent_router, Intent, IntentRouter
from omniagent.core.observability.business.scoring import business_observability
import time


@dataclass
class OrchestratorResult:
    intent: str
    plan_name: str
    plan_version: str
    results: dict[str, dict]
    policy: str
    status: str


class Orchestrator:
    """Coordinateur final. Compose Planner + Policy + IntentRouter + AgentManager."""

    def __init__(self, policy: ExecutionPolicy | None = None,
                 planner_registry_=None, intent_router_=None,
                 use_llm_intent: bool = True):
        self.policy = policy or default_policy
        self.planners = planner_registry_ or planner_registry
        # Fallback LLM : si aucun mot-cle ne matche, le router demande au LLM
        self.router = intent_router_ or IntentRouter(use_llm=use_llm_intent)

    async def run(self, user_id: str, user_message: str,
                  context: dict | None = None) -> OrchestratorResult:
        context = context or {}
        intent = await self.router.aroute(user_message)
        if intent == Intent.UNKNOWN:
            return OrchestratorResult(
                intent="unknown", plan_name="", plan_version="",
                results={}, policy=type(self.policy).__name__, status="unknown_intent",
            )

        planner = self.planners.get_for(intent.value)
        plan = planner.build(intent.value, context)

        # Deterministic guard (Sprint 3+) : on verifie que le plan respecte
        # les invariants deterministes AVANT d executer. Si non, on leve une
        # erreur explicite pour eviter un run non-reproductible.
        from omniagent.core.orchestrator.determinism import assert_deterministic_plan
        try:
            assert_deterministic_plan(plan.steps, plan.name, plan.version)
        except Exception as e:
            # On log et on leve : un plan non-deterministe est un bug
            raise RuntimeError(
                f"Plan non-deterministe refuse (plan={plan.name}@{plan.version}): {e}"
            ) from e

        async def run_step(step, uid: str, ctx: dict) -> dict:
            from omniagent.agents.manager.runner import agent_manager
            t0 = time.monotonic()
            run = await agent_manager.run(
                step.agent_name, uid,
                {"step": step.input_template, "context": ctx},
            )
            duration_ms = (time.monotonic() - t0) * 1000.0
            # Instrumentation business (V1) : cout et business_value sont enrichis
            # par le runner (a partir de l output du sub-agent et des tables costs/value).
            success = run.status.value == "success"
            business_observability.record_run(
                agent_name=step.agent_name,
                success=success,
                duration_ms=duration_ms,
                cost_usd=run.cost_usd,
                business_value=run.business_value,
            )
            if not success:
                business_observability.record_anomaly(step.agent_name)
            return {"status": run.status.value, "output": run.output, "error": run.error}

        results = await self.policy.execute(plan, run_step, user_id, context)
        status = "completed" if all(
            r.get("status") == "success" for r in results.values()
        ) else "partial"
        return OrchestratorResult(
            intent=intent.value, plan_name=plan.name, plan_version=plan.version,
            results=results, policy=type(self.policy).__name__, status=status,
        )


# Singleton partage par main.py / routes / orchestrator/run.
orchestrator = Orchestrator()

# Alias historique (utilise dans les tests et la doc V3) :
#   from omniagent.core.orchestrator.orchestrator import orchestrator_v3
orchestrator_v3 = orchestrator
