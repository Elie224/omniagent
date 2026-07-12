"""Middleware tenant : injecte le scope (tenant_id, user_id) dans les backends memoire.

V2 (Sprint 2a fix) : on resout l utilisateur en lisant les headers de la requete
directement (request.headers), pas via l appel direct a get_current_user
(qui depend du systeme d injection de dependances FastAPI et ne fonctionne
pas quand on l appelle a la main avec juste `request`).

Priorite de resolution (meme regles que auth/dependencies.py) :
1. `Authorization: Bearer <jwt>` -> decode, sub=user_id, org_id=tenant_id
2. `X-User` + `X-Role` (dev/test) -> user_id=x_user, tenant_id="default"
3. Aucun -> fallback dev "demo"/"default"

Le scope est pose *avant* le handler puis reinitialise au scope precedent
apres la requete (defense en profondeur contre les fuites entre requetes).
"""
from __future__ import annotations
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from omniagent.auth.service import decode_token, InvalidTokenError
from omniagent.core.security.rbac import Role


log = logging.getLogger("tenancy")


def _resolve_user_from_request(request: Request):
    """Resout l utilisateur directement via les headers de la requete."""
    headers = request.headers
    authz = headers.get("authorization") or headers.get("Authorization")
    if authz:
        token = authz[7:].strip() if authz.lower().startswith("bearer ") else ""
        if token:
            try:
                payload = decode_token(token, expected_type="access")
                user_id = payload.get("sub")
                tenant_id = payload.get("org_id", "default")
                role_str = payload.get("role", "user")
                if user_id:
                    try:
                        role = Role(role_str)
                    except ValueError:
                        role = Role.USER
                    return _UserLite(user_id=user_id, tenant_id=tenant_id, role=role)
            except InvalidTokenError:
                pass  # Bearer invalide -> on tente legacy

    x_user = headers.get("x-user") or headers.get("X-User")
    if x_user:
        x_role = headers.get("x-role") or headers.get("X-Role")
        from omniagent.core.config import settings
        if settings.env != "production":
            role_value = x_role or ("admin" if settings.env != "production" else "user")
            try:
                role = Role(role_value)
            except ValueError:
                role = Role.USER
            return _UserLite(user_id=x_user, tenant_id="default", role=role)

    # Fallback dev
    from omniagent.core.config import settings
    if settings.env != "production":
        return _UserLite(user_id="demo", tenant_id="default", role=Role.ADMIN)
    return None


class _UserLite:
    """Objet leger compatible avec TenantScopeMiddleware._apply_scope."""
    __slots__ = ("user_id", "tenant_id", "role")

    def __init__(self, user_id: str, tenant_id: str, role: Role):
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.role = role


class TenantScopeMiddleware(BaseHTTPMiddleware):
    """Pousse le scope tenant/user dans les backends memoire avant chaque requete."""

    async def dispatch(self, request: Request, call_next) -> Response:
        memory_stack = getattr(request.app.state, "memory_stack", None)
        if memory_stack is None:
            return await call_next(request)

        previous = self._snapshot_scope(memory_stack)

        # Snapshot du tenant contexte event_bus pour le restorer en fin de requete
        event_bus = getattr(request.app.state, "event_bus", None)
        previous_event_tenant = None
        if event_bus is not None and hasattr(event_bus, "_tenant_context"):
            previous_event_tenant = dict(event_bus._tenant_context)

        try:
            user = _resolve_user_from_request(request)
            if user is not None:
                self._apply_scope(memory_stack, user)
                if event_bus is not None and hasattr(event_bus, "set_tenant_context"):
                    event_bus.set_tenant_context(tenant_id=user.tenant_id)
        except Exception as e:
            log.debug(f"TenantScope skip: {e}")

        try:
            return await call_next(request)
        finally:
            self._restore_scope(memory_stack, previous)
            if event_bus is not None and previous_event_tenant is not None and hasattr(event_bus, "_tenant_context"):
                event_bus._tenant_context = previous_event_tenant

    @staticmethod
    def _apply_scope(memory_stack, user) -> None:
        uid = getattr(user, "user_id", None) or "demo"
        tid = getattr(user, "tenant_id", None) or "default"
        if hasattr(memory_stack.user, "set_scope"):
            memory_stack.user.set_scope(uid, tid)
        if hasattr(memory_stack.vector, "set_scope"):
            memory_stack.vector.set_scope(uid, tid)

    @staticmethod
    def _snapshot_scope(memory_stack) -> dict:
        snap = {}
        for name in ("user", "vector"):
            backend = getattr(memory_stack, name, None)
            if backend is None:
                continue
            snap[name] = (
                getattr(backend, "_user", None),
                getattr(backend, "_tenant", None),
            )
        return snap

    @staticmethod
    def _restore_scope(memory_stack, snap: dict) -> None:
        for name, val in snap.items():
            backend = getattr(memory_stack, name, None)
            if backend is None or not val or not hasattr(backend, "set_scope"):
                continue
            u, t = val
            backend.set_scope(u or "demo", t or "default")