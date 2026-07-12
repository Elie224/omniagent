"""Execution policies : regles pour executer un plan.

- ParallelPolicy   : lance les steps en parallele
- SequentialPolicy : execute les steps un par un
- AdaptivePolicy   : decide selon les dependencies et la charge
"""
from __future__ import annotations
import asyncio
from abc import ABC, abstractmethod
from typing import Any, Callable

from omniagent.core.orchestrator.planner.base import Plan, PlanStep


class ExecutionPolicy(ABC):
    @abstractmethod
    async def execute(self, plan: Plan, run_step: Callable,
                       user_id: str, context: dict) -> dict:
        """Execute le plan selon la policy. Retourne les resultats par agent."""


class SequentialPolicy(ExecutionPolicy):
    async def execute(self, plan: Plan, run_step, user_id: str, context: dict) -> dict:
        results: dict[str, dict] = {}
        for step in plan.steps:
            r = await run_step(step, user_id, context)
            results[step.agent_name] = r
            context = {**context, "prev": r.get("output", {}), step.agent_name: r}
            if r.get("status") != "success":
                break
        return results


class ParallelPolicy(ExecutionPolicy):
    """Lance en parallele tous les steps qui peuvent l etre."""

    def __init__(self, max_concurrency: int = 5):
        self._max = max_concurrency

    async def execute(self, plan: Plan, run_step, user_id: str, context: dict) -> dict:
        results: dict[str, dict] = {}
        sem = asyncio.Semaphore(self._max)
        done: set[str] = set()
        pending_tasks: dict[asyncio.Task, PlanStep] = {}

        async def run_with_sem(step: PlanStep) -> tuple[str, dict]:
            async with sem:
                r = await run_step(step, user_id, context)
                return step.agent_name, r

        # Boucle : tant qu il y a des steps a executer
        max_iter = 100
        while plan.next_runnable(done) and max_iter > 0:
            max_iter -= 1
            runnable = plan.next_runnable(done)
            for step in runnable:
                task = asyncio.create_task(run_with_sem(step))
                pending_tasks[task] = step
            if not pending_tasks:
                break
            done_set, _ = await asyncio.wait(
                pending_tasks.keys(),
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done_set:
                agent_name, r = task.result()
                results[agent_name] = r
                done.add(agent_name)
                if r.get("status") == "success":
                    context[agent_name] = r
                del pending_tasks[task]
            if any(r.get("status") not in {"success", "skipped"} for r in results.values()):
                break
        return results


class AdaptivePolicy(ExecutionPolicy):
    """Sequentiel pour les steps a forte dependance, parallele pour les autres."""

    def __init__(self, parallel_threshold: int = 2):
        self._sequential = SequentialPolicy()
        self._parallel = ParallelPolicy()
        self._threshold = parallel_threshold

    async def execute(self, plan: Plan, run_step, user_id: str, context: dict) -> dict:
        # Si plusieurs steps sont independants -> parallel
        independent = [s for s in plan.steps if not s.depends_on]
        if len(independent) >= self._threshold:
            return await self._parallel.execute(plan, run_step, user_id, context)
        return await self._sequential.execute(plan, run_step, user_id, context)


# Policies par defaut
default_policy = AdaptivePolicy()