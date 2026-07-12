"""Re-export des routes Emploi sous /api/v1/employment/..."""
from omniagent.agents.emploi.router import router as _emploi_router
from fastapi import APIRouter

router = APIRouter()
router.include_router(_emploi_router, tags=["employment"])