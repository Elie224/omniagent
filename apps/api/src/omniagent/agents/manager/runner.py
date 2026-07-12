"""Agent Manager : gere le cycle de vie des agents (start, monitor, retry, cancel)."""
import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from omniagent.core.registry.agent_registry import AgentSpec, AgentStatus, registry
from omniagent.core.observability.tracing import tracer
from omniagent.core.observability.metrics import metrics
from omniagent.core.observability.costs import get_cost
from omniagent.core.observability.business.value import compute_business_value
from omniagent.core.models.router import model_router, QuotaExceededError


@dataclass
class AgentRun:
    run_id: str
    agent_name: str
    user_id: str
    input: dict
    status: AgentStatus = AgentStatus.IDLE
    output: Any = None
    error: str | None = None
    started_at: float = 0.0
    finished_at: float = 0.0
    retries: int = 0
    span_id: str | None = None
    # Observabilite business (V1) : remplis par le runner apres execution.
    # Les sub-agents peuvent les fournir dans leur dict de retour (`model`, `tokens`)
    # sinon on les laisse aux valeurs par defaut.
    model: str = "unknown"
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    business_value: float = 0.0


class AgentManager:
    """Demarre, supervise et gere les reprises des agents."""

    def __init__(self, max_retries: int = 3, retry_delay_s: float = 2.0):
        self._runs: dict[str, AgentRun] = {}
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._max_retries = max_retries
        self._retry_delay = retry_delay_s

    def _get_semaphore(self, agent_name: str, max_conc: int) -> asyncio.Semaphore:
        if agent_name not in self._semaphores:
            self._semaphores[agent_name] = asyncio.Semaphore(max_conc)
        return self._semaphores[agent_name]

    async def run(self, agent_name: str, user_id: str, input_data: dict) -> AgentRun:
        spec = registry.get(agent_name)
        sem = self._get_semaphore(agent_name, spec.max_concurrency)
        await sem.acquire()
        run = AgentRun(run_id=str(uuid.uuid4()), agent_name=agent_name,
                       user_id=user_id, input=input_data)
        self._runs[run.run_id] = run
        try:
            await self._execute(run, spec)
        finally:
            sem.release()
        return run

    async def _execute(self, run: AgentRun, spec: AgentSpec) -> None:
        run.status = AgentStatus.RUNNING
        run.started_at = time.time()
        with tracer.span(f"agent.{spec.name}", user_id=run.user_id, run_id=run.run_id) as sp:
            run.span_id = sp.name
            for attempt in range(self._max_retries + 1):
                try:
                    model_router.check_quota(run.user_id)
                    run.output = await spec.run_fn(run.input, run.user_id)
                    _enrich_run_metrics(run, spec)
                    run.status = AgentStatus.SUCCESS
                    metrics.counter(f"agent.{spec.name}.success").inc()
                    break
                except QuotaExceededError as e:
                    run.status = AgentStatus.FAILED
                    run.error = str(e)
                    metrics.counter(f"agent.{spec.name}.quota_exceeded").inc()
                    break
                except Exception as e:
                    run.retries = attempt
                    if attempt < self._max_retries:
                        run.status = AgentStatus.RETRYING
                        await asyncio.sleep(self._retry_delay * (attempt + 1))
                    else:
                        run.status = AgentStatus.FAILED
                        run.error = str(e)
                        metrics.counter(f"agent.{spec.name}.failed").inc()
            run.finished_at = time.time()
            sp.attributes["status"] = run.status.value
            sp.attributes["duration_ms"] = sp.duration_ms()

    def get_run(self, run_id: str) -> AgentRun | None:
        return self._runs.get(run_id)

    def list_runs(self, user_id: str | None = None) -> list[AgentRun]:
        runs = self._runs.values()
        if user_id:
            runs = [r for r in runs if r.user_id == user_id]
        return list(runs)



def _enrich_run_metrics(run: "AgentRun", spec: "AgentSpec") -> None:
    """Extrait model/tokens depuis l output du sub-agent et calcule cout + business_value.

    Le sub-agent peut emettre un dict de la forme :
        {"status": "ok", "output": <X>, "model": "gpt-4o", "tokens": {"in": 1200, "out": 300}}
    ou juste un output libre (mocks). On extrait ce qu on peut, le reste tombe a 0.
    """
    out = run.output
    if isinstance(out, dict):
        run.model = str(out.get("model", run.model))
        tokens = out.get("tokens")
        if isinstance(tokens, dict):
            run.tokens_in = int(tokens.get("in", tokens.get("input", 0)) or 0)
            run.tokens_out = int(tokens.get("out", tokens.get("output", 0)) or 0)
        # output peut lui-meme etre un dict avec les metriques (cas sub-agent qui suit le contrat)
        inner = out.get("output")
        if isinstance(inner, dict):
            run.business_value = compute_business_value(spec.name, inner)
        else:
            run.business_value = compute_business_value(spec.name, out)
    else:
        # output non-dict (str, list, None) : pas d extraction, business_value par defaut
        run.business_value = compute_business_value(spec.name, out)
    run.cost_usd = get_cost(run.model, run.tokens_in, run.tokens_out)

agent_manager = AgentManager()