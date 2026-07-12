"""Application FastAPI principale - architecture refactoree."""
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Request, Request
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
    # DB (no-op si Alembic gere le schema, sinon create_all)
    try:
        from omniagent.core.models import init_db
        await init_db()
    except Exception as e:
        print(f"[lifespan] init_db ignore: {e}")
    register_all()
    register_all_agents()
    # Memory stack global (acces via app.state)
    from omniagent.core.database import SessionLocal
    from omniagent.core.memory.factory import build_memory_stack
    app.state.db_session_factory = SessionLocal  # pour auth + routes metier
    app.state.memory_stack = build_memory_stack(db_session=SessionLocal)

    # EventStore persistant : selectionne le backend via settings.event_store_backend
    # (memory par defaut = zero impact, sqlite opt-in pour la persistance).
    from omniagent.core.events.bus import build_event_bus, event_bus
    app.state.event_bus = build_event_bus()
    yield
    # Cleanup : ferme le store si besoin
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

# Ordre des middlewares (du plus externe au plus interne) :
#   TenantScope  -> resout le user et set le scope memoire avant tout
#   Idempotency  -> lit Idempotency-Key, peut reutiliser get_current_user
#   CORS         -> expose les headers
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
async def get_metrics(_user: CurrentUser = Depends(get_current_user)):
    """Endpoint de supervision (authentifie : reserve aux operateurs)."""
    return metrics.snapshot()


class OrchestratorRunRequest(BaseModel):
    message: str
    context: dict = Field(default_factory=dict)


@app.post("/orchestrator/run")
async def orchestrator_run(req: OrchestratorRunRequest, request: Request, user: CurrentUser = Depends(get_current_user)):
    """Point d entree unique de l orchestrateur V3 (Planner + Policy + IntentRouter).

    Le user_id est resolu cote serveur depuis le CurrentUser : on ne peut pas
    executer un plan au nom d un autre utilisateur (coherent avec la regle
    Sprint 2c appliquee a /business-dashboard).

    Vague B : si le user a un profil candidat sauvegarde, on l injecte
    automatiquement dans le contexte sous la cle `user_profile`. Le CVMatchingAgent
    l utilise pour scorer reellement les offres (au lieu du neutre 0.5).
    """
    from omniagent.core.orchestrator import orchestrator
    from omniagent.agents.emploi.profile import (
        load_profile, profile_to_orchestrator_context,
    )
    ctx = dict(req.context or {})
    # 1) Profil candidat du user (memory user scope)
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
            # Best-effort : pas de profil = pas de matching, pas d erreur 500.
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


