"""Dependances FastAPI pour l authentification (V2 : JWT + multi-tenant).

Ordre de resolution :
1. `Authorization: Bearer <jwt>` (canonique) -> decode + lookup user/org
2. `X-User` + `X-Role` (legacy, dev/test uniquement) -> 401 en production
3. Aucun -> 401 (sauf en dev, fallback "demo")

Chaque requete authentifiee fournit un `CurrentUser` avec :
- user_id, role, tenant_id (org_id)
- email (optionnel)
- is_authenticated: True
- is_legacy: True si via X-User (header `X-Legacy-Auth: true` ajoute a la reponse)
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import logging

from fastapi import Depends, Header, HTTPException, Request, status

from omniagent.auth.service import (
    AuthError, InvalidTokenError, decode_token, verify_password,
)
from omniagent.auth import repository as auth_repo
from omniagent.core.config import settings
from omniagent.core.security.rbac import Role, has_permission


logger = logging.getLogger(__name__)


@dataclass
class CurrentUser:
    user_id: str
    role: Role
    tenant_id: str = "default"
    email: str = ""
    is_legacy: bool = False
    is_authenticated: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.user_id, "role": self.role.value,
            "tenant_id": self.tenant_id, "email": self.email,
            "is_legacy": self.is_legacy,
        }


# --- Dependances ---
async def _resolve_from_bearer(authorization: str, db) -> Optional[CurrentUser]:
    """Decode un Bearer JWT et retourne le CurrentUser correspondant."""
    if not authorization.lower().startswith("bearer "):
        return None
    token = authorization[7:].strip()
    if not token:
        return None
    try:
        payload = decode_token(token, expected_type="access")
    except InvalidTokenError:
        return None
    user_id = payload.get("sub")
    org_id = payload.get("org_id", "default")
    role_str = payload.get("role", "user")
    if not user_id:
        return None
    # Lookup user (pour valider qu il existe et est actif)
    user = await auth_repo.get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        return None
    try:
        role = Role(role_str)
    except ValueError:
        role = Role.USER
    return CurrentUser(
        user_id=user_id, role=role, tenant_id=org_id,
        email=user.email, is_legacy=False, is_authenticated=True,
    )


def _resolve_from_legacy(x_user: Optional[str], x_role: Optional[str]) -> Optional[CurrentUser]:
    """Legacy dev headers. Refuse en production."""
    if not x_user:
        return None
    if settings.env == "production":
        return None
    role_value = x_role or ("admin" if settings.env != "production" else "user")
    try:
        role = Role(role_value)
    except ValueError:
        role = Role.USER
    return CurrentUser(
        user_id=x_user, role=role, tenant_id="default",
        email="", is_legacy=True, is_authenticated=True,
    )


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    x_user: Optional[str] = Header(default=None, alias="X-User"),
    x_role: Optional[str] = Header(default=None, alias="X-Role"),
) -> CurrentUser:
    """Resout l utilisateur courant.

    Priorite : Bearer JWT > X-User legacy > fallback dev > 401.
    """
    # 1) Bearer JWT
    if authorization:
        db = request.app.state.db_session_factory
        async with db() as session:
            user = await _resolve_from_bearer(authorization, session)
        if user is not None:
            return user

    # 2) Legacy headers (dev/test UNIQUEMENT)
    # En production, les headers X-User/X-Role sont systematiquement refuses,
    # meme si allow_legacy_headers=True (defense en profondeur : un attaquant
    # ne doit pas pouvoir usurper un user via ces headers en prod).
    if settings.env != "production" and settings.allow_legacy_headers and x_user:
        u = _resolve_from_legacy(x_user, x_role)
        if u is not None:
            return u

    # 3) Fallback dev : si pas de header et pas en prod -> demo
    if settings.env != "production":
        logger.warning("Auth fallback demo active (env=%s, request_path=%s)", settings.env, request.url.path)
        return CurrentUser(
            user_id="demo", role=Role.ADMIN, tenant_id="default",
            email="demo@omniagent.local", is_legacy=True, is_authenticated=True,
        )

    # 4) Production stricte
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentification requise (Authorization: Bearer <jwt>)",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_module_access(module: str, agent: str):
    """Fabrique une dependance qui verifie le RBAC pour (module, agent)."""
    def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not has_permission(user.role, module, agent):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acces refuse : role {user.role.value} ne peut pas utiliser {agent}",
            )
        return user
    return _dep
