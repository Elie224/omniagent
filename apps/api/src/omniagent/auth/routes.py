"""Routes auth : signup, login, refresh, me, logout.

Toutes les routes ecritent dans l audit log via `AuditLog.log()`.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from omniagent.auth import repository as auth_repo
import os
import functools
from omniagent.auth import repository_memory as _auth_repo_mem


def _strip_db(fn):
    """Droppe le premier arg positionnel (le `db` legacy) avant d appeler fn."""
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        return await fn(*args[1:], **kwargs)
    return wrapper


# Wrappers dedies : mappent les kwargs du repo DB vers le repo in-memory.

async def _create_user(db, email, password_hash=None, display_name="", **_):
    return await _auth_repo_mem.create_user(
        email=email, password=password_hash, display_name=display_name,
    )


async def _store_refresh_token(db, jti, user_id, org_id, token_hash, expires_at, **_):
    return await _auth_repo_mem.store_refresh_token(
        jti=jti, user_id=user_id, expires_at=expires_at,
    )


async def _get_refresh_token(db, jti, **_):
    return await _auth_repo_mem.get_refresh_token(jti=jti)


async def _revoke_refresh_token(db, jti, **_):
    return await _auth_repo_mem.revoke_refresh_token(jti=jti)


async def _revoke_all_user_tokens(db, user_id, **_):
    _auth_repo_mem._store.refresh_tokens.clear()
    return 0


async def _get_membership(db, user_id, org_id, **_):
    ms = [m for m in _auth_repo_mem._store.memberships
          if m["user_id"] == user_id and m["org_id"] == org_id]
    return ms[0] if ms else None


async def _noop_last_login(*a, **k):
    return None


_FORCE_MEMORY = os.getenv("OMNIAGENT_FORCE_MEMORY", "").lower() in ("1", "true", "yes")
if _FORCE_MEMORY:
    auth_repo.get_user_by_email       = _strip_db(_auth_repo_mem.get_user_by_email)
    auth_repo.get_user_by_id          = _strip_db(_auth_repo_mem.get_user_by_id)
    auth_repo.create_user             = _create_user
    auth_repo.verify_user_credentials = _strip_db(_auth_repo_mem.verify_user_credentials)
    auth_repo.create_organization     = _strip_db(_auth_repo_mem.create_organization)
    auth_repo.get_organization        = _strip_db(_auth_repo_mem.get_organization)
    auth_repo.create_membership       = _strip_db(_auth_repo_mem.add_membership)
    auth_repo.get_membership          = _get_membership
    auth_repo.list_user_orgs          = _strip_db(_auth_repo_mem.get_memberships)
    auth_repo.update_last_login       = _noop_last_login
    auth_repo.store_refresh_token     = _store_refresh_token
    auth_repo.get_refresh_token       = _get_refresh_token
    auth_repo.revoke_refresh_token    = _revoke_refresh_token
    auth_repo.revoke_all_user_tokens  = _revoke_all_user_tokens
    auth_repo.create_api_key          = _strip_db(_auth_repo_mem.create_api_key)
    auth_repo.get_api_key             = _strip_db(_auth_repo_mem.get_api_key)

from omniagent.auth.dependencies import CurrentUser, get_current_user
from omniagent.core.security.audit import AuditAction, AuditLog
from omniagent.auth.service import (
    AuthError, create_access_token, create_refresh_token,
    decode_token, hash_password, hash_refresh_token,
    InvalidTokenError, verify_password,
)


router = APIRouter()


# --- Schemas ---
class SignupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=128)
    display_name: str = ""
    org_name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: str
    password: str
    org_id: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class UserResponse(BaseModel):
    user_id: str
    email: str
    display_name: str
    org_id: str
    role: str


# --- Routes ---


def _client_ip(request: Request) -> str | None:
    """IP du client (best-effort, X-Forwarded-For en priorite)."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _audit(request: Request, user_id: str, action: AuditAction,
            tenant_id: str = "default", payload: dict | None = None) -> None:
    """Ecrit une entree d audit (print JSON, insertion DB best-effort)."""
    AuditLog(db_session=None).log(
        user_id=user_id, action=action, payload=payload or {},
        tenant_id=tenant_id, ip=_client_ip(request),
    )


@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup(req: SignupRequest, request: Request):
    """Cree un user + une organization, retourne access+refresh tokens."""
    db_factory = request.app.state.db_session_factory
    async with db_factory() as db:
        existing = await auth_repo.get_user_by_email(db, req.email)
        if existing is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Email deja utilise")

        user = await auth_repo.create_user(
            db, email=req.email, password_hash=hash_password(req.password),
            display_name=req.display_name,
        )
        org = await auth_repo.create_organization(db, name=req.org_name)
        await auth_repo.create_membership(db, user.user_id, org.org_id, role="admin")

        access, expires_in = create_access_token(user.user_id, org.org_id, "admin")
        refresh, token_id, exp = create_refresh_token(user.user_id, org.org_id)
        await auth_repo.store_refresh_token(
            db, token_id, user.user_id, org.org_id,
            hash_refresh_token(refresh), exp,
        )

    _audit(request, user_id=user.user_id, action=AuditAction.AUTH_SIGNUP,
           tenant_id=org.org_id, payload={"email": req.email, "org": req.org_name})
    return TokenResponse(access_token=access, refresh_token=refresh, expires_in=expires_in)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, request: Request):
    """Verifie email/password, retourne access+refresh tokens."""
    db_factory = request.app.state.db_session_factory
    async with db_factory() as db:
        user = await auth_repo.get_user_by_email(db, req.email)
        if user is None or not getattr(user, "is_active", True):
            _audit(request, user_id=req.email, action=AuditAction.AUTH_LOGIN_FAILED,
                   payload={"email": req.email, "reason": "unknown_or_inactive"})
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Identifiants invalides")
        if not verify_password(req.password, user.password_hash):
            _audit(request, user_id=req.email, action=AuditAction.AUTH_LOGIN_FAILED,
                   payload={"email": req.email, "reason": "bad_password"})
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Identifiants invalides")

        orgs = await auth_repo.list_user_orgs(db, user.user_id)
        if not orgs:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Aucune organisation")
        if req.org_id:
            m = next((m for m in orgs if m.org_id == req.org_id), None)
            if m is None:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Pas membre de cette org")
        else:
            m = orgs[0]

        await auth_repo.update_last_login(db, user.user_id)
        access, expires_in = create_access_token(user.user_id, m.org_id, m.role)
        refresh, token_id, exp = create_refresh_token(user.user_id, m.org_id)
        await auth_repo.store_refresh_token(
            db, token_id, user.user_id, m.org_id,
            hash_refresh_token(refresh), exp,
        )

    _audit(request, user_id=user.user_id, action=AuditAction.AUTH_LOGIN,
           tenant_id=m.org_id, payload={"email": req.email, "role": m.role})
    return TokenResponse(access_token=access, refresh_token=refresh, expires_in=expires_in)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest, request: Request):
    """Rotation : un nouveau access + un nouveau refresh, l ancien est revoque."""
    try:
        payload = decode_token(req.refresh_token, expected_type="refresh")
    except InvalidTokenError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Refresh invalide: {e}")

    token_id = payload.get("jti")
    user_id = payload.get("sub")
    org_id = payload.get("org_id")
    if not all([token_id, user_id, org_id]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh incomplet")

    db_factory = request.app.state.db_session_factory
    async with db_factory() as db:
        stored = await auth_repo.get_refresh_token(db, token_id)
        if stored is None or stored.revoked_at is not None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh revoque ou inconnu")
        if stored.user_id != user_id or stored.org_id != org_id:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh mismatch")
        if stored.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh expire")
        if stored.token_hash != hash_refresh_token(req.refresh_token):
            await auth_repo.revoke_all_user_tokens(db, user_id)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh hash mismatch")

        m = await auth_repo.get_membership(db, user_id, org_id)
        role = m.role if m else "user"

        access, expires_in = create_access_token(user_id, org_id, role)
        new_refresh, new_token_id, exp = create_refresh_token(user_id, org_id)
        await auth_repo.store_refresh_token(
            db, new_token_id, user_id, org_id,
            hash_refresh_token(new_refresh), exp,
        )
        await auth_repo.revoke_refresh_token(db, token_id)

    _audit(request, user_id=user_id, action=AuditAction.AUTH_REFRESH,
           tenant_id=org_id, payload={"new_token_id": new_token_id})
    return TokenResponse(access_token=access, refresh_token=new_refresh, expires_in=expires_in)


@router.post("/logout")
async def logout(request: Request, user: CurrentUser = Depends(get_current_user)):
    """Revoque tous les refresh tokens de l utilisateur courant."""
    db_factory = request.app.state.db_session_factory
    async with db_factory() as db:
        count = await auth_repo.revoke_all_user_tokens(db, user.user_id)
    _audit(request, user_id=user.user_id, action=AuditAction.AUTH_LOGOUT,
           tenant_id=user.tenant_id, payload={"tokens_revoked": count})
    return {"revoked": count}


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser = Depends(get_current_user), request: Request = None):
    """Retourne le profil de l utilisateur courant (user_id, email, org, role)."""
    db_factory = request.app.state.db_session_factory
    async with db_factory() as db:
        u = await auth_repo.get_user_by_id(db, user.user_id)
        if u is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "User introuvable")
        m = await auth_repo.get_membership(db, user.user_id, user.tenant_id)
    return UserResponse(
        user_id=u.user_id, email=u.email, display_name=u.display_name,
        org_id=user.tenant_id, role=(m.role if m else user.role.value),
    )


@router.get("/health")
async def health():
    return {"module": "auth", "status": "ok"}
