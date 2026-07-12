"""Application FastAPI principale - architecture refactoree."""
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from omniagent.core.config import settings
from omniagent.core.logging import configure_logging
from omniagent.core.observability.metrics import metrics
from omniagent.core.security.audit import AuditLog
from omniagent.auth.dependencies import CurrentUser, get_current_user
from omniagent.api.v1.router import v1
from omniagent.routes import router as root_router

from omniagent.connectors.bootstrap import register_all
from omniagent.agents.manager.registration import register_all_agents


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    try:
        from omniagent.core.models import init_db
        await init_db()
    except Exception as e:
        print(f"[lifespan] init_db ignore: {e}")
    register_all()
    register_all_agents()
    from omniagent.core.database import SessionLocal
    from omniagent.core.memory.factory import build_memory_stack
    app.state.db_session_factory = SessionLocal
    app.state.memory_stack = build_memory_stack(db_session=SessionLocal)
    from omniagent.core.events.bus import build_event_bus, event_bus
    app.state.event_bus = build_event_bus()
    yield
    store = getattr(app.state.event_bus, "_store", None)
    if store is not None and hasattr(store, "close"):
        try:
            await store.close()
        except Exception:
            pass
    metrics.snapshot()


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan,
    docs_url="/docs" if settings.env != "production" else None,
    openapi_url="/openapi.json",
)

from omniagent.tenancy import TenantScopeMiddleware
from omniagent.core.idempotency import IdempotencyMiddleware

app.add_middleware(IdempotencyMiddleware)
app.add_middleware(TenantScopeMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(root_router)
app.include_router(v1)


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.env, "version": settings.version,
            "modules": settings.active_modules}


@app.get("/metrics")
async def get_metrics():
    return metrics.snapshot()


class OrchestratorRunRequest(BaseModel):
    user_id: str = "demo"
    message: str
    context: dict = Field(default_factory=dict)


@app.post("/orchestrator/run")
async def orchestrator_run(req: OrchestratorRunRequest, request: Request, user: CurrentUser = Depends(get_current_user)):
    """Point d entree principal de l orchestrateur V3 (Planner + Policy + IntentRouter)."""
    from omniagent.core.orchestrator import orchestrator
    from omniagent.agents.emploi.profile import (
        load_profile, profile_to_orchestrator_context,
    )
    ctx = dict(req.context or {})
    stack = getattr(request.app.state, "memory_stack", None)
    if stack is not None:
        try:
            user_mem = stack.user
            if hasattr(user_mem, "aget"):
                profile = await user_mem.aget(
                    "profile:candidate",
                    user_id=user.user_id, tenant_id=user.tenant_id,
                )
            else:
                profile = user_mem.get("profile:candidate")
            if profile:
                ctx["user_profile"] = profile_to_orchestrator_context(profile)
        except Exception:
            pass
    result = await orchestrator.run(user.user_id, req.message, ctx)
    return {
        "intent": result.intent,
        "plan": result.plan_name,
        "plan_version": result.plan_version,
        "policy": result.policy,
        "status": result.status,
        "results": result.results,
        "user_profile_injected": "user_profile" in ctx,
    }


class OrchestratorWorkflowRequest(BaseModel):
    """Requete explicite pour declencher le workflow Emploi structure (DAG)."""
    workflow: str = "job_workflow"
    context: dict = Field(default_factory=dict)
    dry_run: bool = True


@app.post("/orchestrator/workflow")
async def orchestrator_workflow(req: OrchestratorWorkflowRequest, request: Request, user: CurrentUser = Depends(get_current_user)):
    """Point d entree dedie au JobWorkflowPlanner (pipeline Emploi en DAG, 7 etapes).

    Declenche directement le plan structure (discovery -> filter -> enrich -> match
    -> cv -> template -> apply) sans passer par l IntentRouter.

    Branchements transverses :
    - Profil candidat injecte depuis la memoire user
    - Business observability : chaque etape est enregistree avec tenant_id
    - Monitoring transverse : compte-rendu global du run
    """
    from omniagent.agents.emploi.workflow.planner import job_workflow_planner
    from omniagent.agents.emploi.workflow import JOB_AGENTS
    from omniagent.core.observability.business.scoring import business_observability
    from omniagent.agents.transverse.subagents.monitoring_agent import run as monitoring_run
    import time

    plan = job_workflow_planner.build("job_workflow_run", dict(req.context or {}))
    ctx = dict(req.context or {})
    ctx["dry_run"] = req.dry_run
    ctx["tenant_id"] = user.tenant_id
    ctx["user_id"] = user.user_id

    stack = getattr(request.app.state, "memory_stack", None)
    if stack is not None:
        try:
            user_mem = stack.user
            if hasattr(user_mem, "aget"):
                profile = await user_mem.aget(
                    "profile:candidate", user_id=user.user_id, tenant_id=user.tenant_id
                )
            else:
                profile = user_mem.get("profile:candidate")
            if profile:
                ctx["user_profile"] = profile
        except Exception:
            pass

    step_outputs: dict = {}
    step_results: dict = {}
    correlation_id = ctx.get("correlation_id") or f"wf-{int(time.time()*1000)}"
    started = time.monotonic()
    overall_status = "completed"
    try:
        for step in plan.steps:
            agent_cls = JOB_AGENTS.get(step.agent_name)
            if agent_cls is None:
                step_results[step.agent_name] = {
                    "status": "skipped",
                    "error": f"unknown sub-agent: {step.agent_name}",
                }
                continue
            agent = agent_cls()
            t0 = time.monotonic()
            try:
                out = await agent.run(
                    {"step": step.input_template, "context": ctx, "previous": step_outputs, "user_id": user.user_id},
                    ctx,
                )
                dur_ms = (time.monotonic() - t0) * 1000.0
                step_outputs[step.agent_name] = out
                step_results[step.agent_name] = {
                    "status": "success",
                    "output": out,
                    "duration_ms": round(dur_ms, 1),
                }
                business_observability.record_run(
                    agent_name=f"workflow.{step.agent_name}",
                    success=True, duration_ms=dur_ms,
                    tenant_id=user.tenant_id,
                )
            except Exception as e:
                dur_ms = (time.monotonic() - t0) * 1000.0
                step_results[step.agent_name] = {
                    "status": "failed",
                    "error": str(e),
                    "duration_ms": round(dur_ms, 1),
                }
                business_observability.record_run(
                    agent_name=f"workflow.{step.agent_name}",
                    success=False, duration_ms=dur_ms,
                    tenant_id=user.tenant_id,
                )
                overall_status = "partial"
                break
    finally:
        total_ms = (time.monotonic() - started) * 1000.0

    try:
        await monitoring_run({
            "action": "record",
            "agent_name": "job_workflow",
            "status": "success" if overall_status == "completed" else "partial",
            "run_id": correlation_id,
            "payload": {
                "tenant_id": user.tenant_id,
                "user_id": user.user_id,
                "duration_ms": round(total_ms, 1),
                "steps": list(step_results.keys()),
                "workflow": req.workflow,
            },
        }, user_id=user.user_id)
    except Exception:
        pass

    return {
        "workflow": req.workflow,
        "plan_name": plan.name,
        "plan_version": plan.version,
        "correlation_id": correlation_id,
        "status": overall_status,
        "duration_ms": round(total_ms, 1),
        "steps": step_results,
    }