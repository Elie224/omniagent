"""Application FastAPI principale - architecture refactoree."""
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from omniagent.core.config import settings
from omniagent.core.logging import configure_logging
from omniagent.core.observability.metrics import metrics
from omniagent.core.security.audit import AuditLog
from omniagent.auth.dependencies import CurrentUser, get_current_user, require_module_access
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
    # Sprint 3 : workflows declaratifs (job_search_dag, cv_refresh, etc.)
    from omniagent.core.orchestrator.workflows import register_default_workflows
    n_wf = register_default_workflows()
    print(f"[lifespan] {n_wf} workflows declaratifs charges")
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
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.env == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    return response

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
    workflow: str = "intent_research"
    context: dict = Field(default_factory=dict)
    dry_run: bool = True


@app.post("/orchestrator/workflow", dependencies=[Depends(require_module_access("emploi", "agent_mission_controller"))])
async def orchestrator_workflow(req: OrchestratorWorkflowRequest, request: Request, user: CurrentUser = Depends(get_current_user)):
    """Point d entree unique pour executer un workflow declaratif."""
    import time
    from omniagent.core.orchestrator.workflows import workflow_registry
    from omniagent.core.observability.business.scoring import business_observability
    from omniagent.agents.transverse.subagents.monitoring_agent import run as monitoring_run

    wf = workflow_registry.get(req.workflow)
    if wf is None:
        raise HTTPException(
            status_code=404,
            detail=f"workflow inconnu: {req.workflow}. Disponibles: {workflow_registry.names()}",
        )

    # Incident response: les anciens workflows "job_*" restent non alignes
    # avec les garde-fous mission controller; on les bloque explicitement.
    blocked_legacy_workflows = {"job_workflow", "job_search_dag", "job_search_quick", "cv_refresh"}
    if req.workflow in blocked_legacy_workflows:
        raise HTTPException(
            status_code=403,
            detail="workflow legacy bloque (utiliser /api/v1/employment/mission/run)",
        )

    if not req.dry_run:
        raise HTTPException(
            status_code=403,
            detail="orchestrator/workflow impose dry_run=true (envoi reel via /api/v1/employment/mission/run)",
        )

    ctx = dict(req.context or {})
    ctx["dry_run"] = req.dry_run
    ctx["tenant_id"] = user.tenant_id
    ctx["user_id"] = user.user_id
    ctx["user_role"] = user.role.value
    ctx["workflow"] = wf.name
    ctx["workflow_version"] = wf.version

    stack = getattr(request.app.state, 'memory_stack', None)
    if stack is not None:
        try:
            user_mem = stack.user
            if hasattr(user_mem, 'aget'):
                profile = await user_mem.aget(
                    "profile:candidate", user_id=user.user_id, tenant_id=user.tenant_id,
                )
            else:
                profile = user_mem.get("profile:candidate")
            if profile:
                ctx["user_profile"] = profile
        except Exception:
            pass

    from omniagent.agents.emploi.workflow import JOB_AGENTS as _JOB
    import importlib

    def _resolve_agent_class(agent_name):
        if agent_name in _JOB:
            return _JOB[agent_name]
        # Strategie de resolution des subagents :
        # 1) nom direct : omniagent.agents.X.subagents.<agent_name>
        # 2) avec suffixe _agent : ...subagents.<agent_name>_agent
        # 3) transverse : ...transverse.subagents.<agent_name>[_agent]
        candidates = set()
        candidates.add(agent_name)
        # Variantes : ajouter/retirer le suffixe _agent
        for v in [agent_name, agent_name.removesuffix("_agent"), agent_name + "_agent",
                  agent_name.removeprefix("agent_"),
                  agent_name.removeprefix("agent_") + "_agent",
                  agent_name.removeprefix("agent_").removesuffix("_agent")]:
            if v:
                candidates.add(v)
        namespaces = [
            "omniagent.agents.emploi.subagents.",
            "omniagent.agents.transverse.subagents.",
        ]
        for ns in namespaces:
            for cand in candidates:
                try:
                    mod = importlib.import_module(ns + cand)
                    fn = getattr(mod, 'run', None)
                    if fn is not None:
                        return fn
                except Exception:
                    continue
        return None

    step_outputs = {}
    step_results = {}
    correlation_id = ctx.get("correlation_id") or f"wf-{int(time.time() * 1000)}"
    started = time.monotonic()
    overall_status = "completed"
    done = set()
    steps_remaining = list(wf.steps)

    try:
        while steps_remaining:
            runnable = [s for s in steps_remaining if all(d in done for d in s.depends_on)]
            if not runnable:
                overall_status = "failed"
                step_results["__dag__"] = {"status": "failed", "error": "aucun step runnable"}
                break
            for step in runnable:
                agent_fn = _resolve_agent_class(step.agent_name)
                if agent_fn is None:
                    step_results[step.name] = {
                        "status": "skipped",
                        "error": f"agent inconnu: {step.agent_name}",
                    }
                    done.add(step.name)
                    steps_remaining.remove(step)
                    continue
                t0 = time.monotonic()
                try:
                    if callable(agent_fn):
                        # Cas 1 : classe (JOB_AGENTS). On instancie et on appelle .run().
                        # Cas 2 : fonction async (subagents emploi/transverse). Appel direct.
                        payload = {
                            "step": step.input_template,
                            "context": ctx,
                            "previous": step_outputs,
                            "user_id": user.user_id,
                        }
                        if not isinstance(agent_fn, type):
                            # Fonction : appel direct async-safe.
                            result = agent_fn(payload, user.user_id)
                            if hasattr(result, "__await__"):
                                out = await result
                            else:
                                out = result
                        else:
                            # Classe : instanciation puis .run()
                            try:
                                inst = agent_fn()
                                if hasattr(inst, "run"):
                                    out = await inst.run(payload, ctx)
                                else:
                                    out = agent_fn(payload, ctx)
                            except Exception:
                                out = agent_fn(payload, ctx)
                    else:
                        out = {"status": "noop"}

                    dur_ms = (time.monotonic() - t0) * 1000.0
                    step_outputs[step.name] = out
                    step_results[step.name] = {
                        "status": "success",
                        "output": out,
                        "duration_ms": round(dur_ms, 1),
                    }
                    business_observability.record_run(
                        agent_name=f"workflow.{step.name}",
                        success=True, duration_ms=dur_ms,
                        tenant_id=user.tenant_id,
                    )
                except Exception as e:
                    dur_ms = (time.monotonic() - t0) * 1000.0
                    step_results[step.name] = {
                        "status": "failed",
                        "error": str(e),
                        "duration_ms": round(dur_ms, 1),
                    }
                    business_observability.record_run(
                        agent_name=f"workflow.{step.name}",
                        success=False, duration_ms=dur_ms,
                        tenant_id=user.tenant_id,
                    )
                    if step.optional:
                        done.add(step.name)
                        steps_remaining.remove(step)
                        continue
                    overall_status = "partial"
                    steps_remaining = []
                    break
                done.add(step.name)
                steps_remaining.remove(step)
    finally:
        total_ms = (time.monotonic() - started) * 1000.0

    try:
        await monitoring_run({
            "action": "record",
            "agent_name": wf.name,
            "status": "success" if overall_status == "completed" else "partial",
            "run_id": correlation_id,
            "payload": {
                "tenant_id": user.tenant_id,
                "user_id": user.user_id,
                "duration_ms": round(total_ms, 1),
                "steps": list(step_results.keys()),
                "workflow_version": wf.version,
            },
        }, user_id=user.user_id)
    except Exception:
        pass

    return {
        "workflow": wf.name,
        "workflow_version": wf.version,
        "description": wf.description,
        "plan_name": wf.name,
        "plan_version": wf.version,
        "correlation_id": correlation_id,
        "status": overall_status,
        "duration_ms": round(total_ms, 1),
        "steps": step_results,
    }

