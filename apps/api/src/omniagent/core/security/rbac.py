"""Role-Based Access Control : 4 roles distincts avec permissions module/agent."""
from enum import Enum
from functools import wraps
from fastapi import HTTPException, status


class Role(str, Enum):
    ADMIN = "admin"
    RECRUITER = "recruiter"          # module Emploi
    USER = "user"                    # acces minimal


# Matrice role -> {module: [agents autorises]}
ROLE_PERMISSIONS: dict[Role, dict[str, list[str]]] = {
    Role.ADMIN: {
        "emploi":       ["*"],
    },
    Role.RECRUITER: {
        "emploi":       ["agent_emploi", "agent_adzuna", "agent_france_travail",
                         "agent_themuse",
                         "agent_cv", "agent_lettre",
                         "agent_interview_coach", "agent_salary_benchmark", "agent_followup",
                         "agent_contact_enrichment", "agent_lettre_requirement", "agent_filtering_matching", "agent_mission_controller", "agent_application_sender"],
    },
    Role.USER: {
        "emploi":       ["agent_emploi", "agent_cv", "agent_lettre",
                         "agent_interview_coach", "agent_salary_benchmark", "agent_followup",
                         "agent_contact_enrichment", "agent_lettre_requirement", "agent_filtering_matching", "agent_mission_controller", "agent_application_sender"],
    },
}


def has_permission(role: Role, module: str, agent: str) -> bool:
    perms = ROLE_PERMISSIONS.get(role, {})
    agents = perms.get(module, [])
    return "*" in agents or agent in agents


def require_permission(module: str, agent: str):
    """Decorator FastAPI : verifie que l''utilisateur a le droit d''acceder a l''agent."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user=None, **kwargs):
            if current_user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentification requise",
                )
            if not has_permission(Role(current_user.role), module, agent):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Acces refuse : role {current_user.role} ne peut pas utiliser {agent}",
                )
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator