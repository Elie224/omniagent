"""Router v1 : agrege les domaines restants (employment, shared, transverse).

Vague B : focus Emploi uniquement. Les modules marketing/recouvrement ont ete retires
du repo. Les routes transverse restent disponibles (memory/knowledge/monitoring/
planning/notification) car elles sont consommees par Emploi (CV, lettre, profil).
"""
from fastapi import APIRouter

from omniagent.core.config import settings


v1 = APIRouter(prefix="/api/v1")


def register_domains(router: APIRouter) -> None:
    from omniagent.api.v1.shared import router as shared
    from omniagent.api.v1.employment import router as employment

    router.include_router(shared,     prefix="/shared",     tags=["shared"])
    # Auth : signup, login, refresh, me, logout (toujours monte)
    from omniagent.auth.routes import router as auth
    router.include_router(auth,        prefix="/auth",       tags=["auth"])

    if "emploi" in settings.active_modules:
        router.include_router(employment, prefix="/employment", tags=["employment"])

    # Module transverse : memory, knowledge, monitoring, planning, notification
    from omniagent.agents.transverse.router import router as transverse
    if "transverse" in settings.active_modules:
        router.include_router(transverse, prefix="/shared", tags=["transverse"])


register_domains(v1)