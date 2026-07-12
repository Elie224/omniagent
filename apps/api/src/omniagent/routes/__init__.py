"""Routes racine (info API).

Vague B : focus Emploi. /modules ne liste que les modules actifs + transverse.
"""
from fastapi import APIRouter

from omniagent.core.config import settings


router = APIRouter()


@router.get("/")
async def root():
    return {
        "name": "OmniAgent API",
        "version": settings.version,
        "modules": settings.active_modules,
        "docs": "/docs",
        "api_v1": "/api/v1",
    }


@router.get("/modules")
async def list_modules():
    """Liste les modules actifs (selon ACTIVE_MODULES dans .env)."""
    active = set(settings.active_modules)
    catalog = {
        "emploi":     {"agents": 6, "platforms": ["linkedin", "indeed", "hellowork"]},
        "transverse": {"agents": 5, "scope": "partage par tous les modules"},
    }
    return {name: meta for name, meta in catalog.items() if name in active}


@router.get("/orchestrator/status")
async def orchestrator_status():
    """Vue rapide de l orchestrateur canonique (planner + policy enregistres)."""
    from omniagent.core.orchestrator import (
        Orchestrator, intent_router, Intent, planner_registry, orchestrator,
    )
    return {
        "policy": type(orchestrator.policy).__name__,
        "planners": len(planner_registry._planners),
        "supported_intents": [i.value for i in Intent],
        "router": type(intent_router).__name__,
        "orchestrator_class": Orchestrator.__name__,
    }