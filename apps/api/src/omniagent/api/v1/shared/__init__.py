"""Routes partagees (auth, health, observabilite, multi-tenant)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from omniagent.core.config import settings
from omniagent.core.events import event_bus, get_event_bus
from omniagent.core.observability.business.scoring import business_observability
from omniagent.tenancy.context import tenant_registry, TenantPlan
from omniagent.auth.dependencies import CurrentUser, get_current_user


router = APIRouter()


@router.get("/health")
async def health():
    return {
        "status": "ok", "env": settings.env, "version": settings.version,
        "modules": settings.active_modules,
    }


@router.get("/metrics")
async def metrics(_user: CurrentUser = Depends(get_current_user)):
    return business_observability.dashboard()


# Dashboard business scope par tenant (cout LLM, ROI, succes, duree).
# Sprint 2c : tenant_id vient du CurrentUser (impossible de le spoofer via query string).
@router.get("/business-dashboard")
async def business_dashboard(user: CurrentUser = Depends(get_current_user)):
    return business_observability.dashboard_for(user.tenant_id)


@router.get("/events/recent")
async def recent_events(limit: int = 50, user_id: str | None = None):
    return get_event_bus().get_history(limit=limit, user_id=user_id)


@router.get("/tenants/{tenant_id}")
async def get_tenant(tenant_id: str):
    t = tenant_registry.get(tenant_id)
    if not t:
        return {"error": "not found"}
    return {
        "tenant_id": t.tenant_id, "name": t.name, "plan": t.plan.value,
        "status": t.status.value, "quotas": t.quotas,
        "usage": tenant_registry.get_usage(tenant_id),
    }


class CreateTenantRequest(BaseModel):
    name: str
    plan: TenantPlan = TenantPlan.FREE


@router.post("/tenants")
async def create_tenant(req: CreateTenantRequest):
    t = tenant_registry.create(req.name, req.plan)
    return {"tenant_id": t.tenant_id, "name": t.name, "plan": t.plan.value}

# Query d events persistants (EventStore) : supporte les filtres par type,
# user_id, correlation_id et `since`. Authentifie : reserve aux operateurs.
# On lit le bus depuis app.state (celui du lifespan), pas le singleton module,
# pour beneficier du store selectionne par build_event_bus().
from fastapi import Request
@router.get("/events/query")
async def events_query(
    request: Request,
    event_type: str | None = None,
    user_id: str | None = None,
    correlation_id: str | None = None,
    limit: int = 100,
    _user: CurrentUser = Depends(get_current_user),
):
    bus = getattr(request.app.state, "event_bus", None) or event_bus
    store = bus.get_store() if hasattr(bus, "get_store") else None
    if store is None:
        return {"events": [], "warning": "event store non initialise"}
    events = await store.query(
        event_type=event_type,
        user_id=user_id,
        correlation_id=correlation_id,
        limit=min(limit, 500),
    )
    return {
        "count": len(events),
        "events": [e.to_dict() for e in events],
    }



# Sprint 3 : tableau de bord workflow par tenant.
# Regroupe les compteurs enregistres par orchestrator_workflow via
# business_observability.record_run(agent_name="workflow.<step>", ...).
@router.get("/workflows/status")
async def workflows_status(user: CurrentUser = Depends(get_current_user)):
    from collections import defaultdict
    tenant_id = user.tenant_id
    by_wf = defaultdict(lambda: {"runs": 0, "successes": 0, "failures": 0, "duration_ms": 0.0})
    scores = getattr(business_observability, "_scores_by_tenant", None) or {}
    for (tid, agent_name), s in scores.items():
        if tid != tenant_id:
            continue
        if not agent_name.startswith("workflow."):
            continue
        wf = agent_name[len("workflow."):]
        b = by_wf[wf]
        # On lit directement les compteurs sur l instance partagee,
        # pas via to_dict() qui expose des champs derives.
        b["runs"]      += int(getattr(s, "runs", 0))
        b["successes"] += int(getattr(s, "successes", 0))
        b["failures"]  += int(getattr(s, "failures", 0))
        b["duration_ms"] += float(getattr(s, "total_duration_ms", 0.0))
    workflows = []
    for wf, agg in by_wf.items():
        runs = agg["runs"] or 0
        workflows.append({
            "workflow": wf,
            "runs": runs,
            "successes": agg["successes"],
            "failures": agg["failures"],
            "success_rate": round(agg["successes"] / runs, 3) if runs else 0.0,
            "avg_duration_ms": round(agg["duration_ms"] / runs, 1) if runs else 0.0,
        })
    workflows.sort(key=lambda x: x["workflow"])
    return {"tenant_id": tenant_id, "count": len(workflows), "workflows": workflows}
