"""Fallback in-memory pour le module auth (utilise quand FORCE_MEMORY=1 ou pas de DB).

API publique identique a `auth.repository`, mais tout reste en memoire du
process. Suffisant pour le dev local et pour les tests sans Postgres.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# State global (en memoire seulement)
# ---------------------------------------------------------------------------

class _AuthStore:
    """Singleton en memoire partagee par le repo."""

    def __init__(self):
        self.users: dict[str, dict] = {}        # user_id -> _UserRow
        self.users_by_email: dict[str, str] = {}  # email -> user_id
        self.orgs: dict[str, dict] = {}        # org_id -> _OrgRow
        self.memberships: list[dict] = []      # _MembershipRow
        self.refresh_tokens: dict[str, dict] = {}  # _RefreshTokenRow
        self.api_keys: dict[str, dict] = {}

    def reset(self):
        self.users.clear()
        self.users_by_email.clear()
        self.orgs.clear()
        self.memberships.clear()
        self.refresh_tokens.clear()
        self.api_keys.clear()


_store = _AuthStore()


def reset_inmemory_auth() -> None:
    """Reinitialise le state in-memory (utile pour les tests)."""
    _store.reset()


# ---------------------------------------------------------------------------
# Password hashing (re-export pour eviter d import circulaire)
# ---------------------------------------------------------------------------

def _hash(password: str) -> str:
    from omniagent.auth.service import hash_password
    return hash_password(password)


def _verify(password: str, hashed: str) -> bool:
    from omniagent.auth.service import verify_password
    return verify_password(password, hashed)


# ---------------------------------------------------------------------------
# Row classes : dicts exposes aussi en attributs (compat ORM SQLAlchemy).
# ---------------------------------------------------------------------------

class _AttrDict(dict):
    """dict classique qui delegue `__getattr__` aux cles du dict.

    Permet d utiliser indifféremment `row["key"]` ou `row.key` comme avec
    une row SQLAlchemy.
    """

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            return None

    def __setattr__(self, name, value):
        self[name] = value


class _UserRow(_AttrDict):
    @property
    def is_active(self) -> bool:
        return self.get("is_active", True)


class _OrgRow(_AttrDict):
    pass


class _MembershipRow(_AttrDict):
    pass


class _RefreshTokenRow(_AttrDict):
    pass


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------

async def create_organization(name: str, plan: str = "free",
                                org_id: Optional[str] = None) -> dict:
    oid = org_id or str(uuid.uuid4())
    row = _OrgRow({
        "org_id": oid,
        "name": name,
        "plan": plan,
        "status": "active",
        "created_at": _now(),
    })
    _store.orgs[oid] = row
    return row


async def get_organization(org_id: str) -> dict | None:
    return _store.orgs.get(org_id)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

async def get_user_by_email(email: str) -> dict | None:
    uid = _store.users_by_email.get(email.lower())
    if uid is None:
        return None
    return _store.users.get(uid)


async def get_user_by_id(user_id: str) -> dict | None:
    return _store.users.get(user_id)


async def create_user(email: str, password: str, display_name: str = "") -> dict:
    """`password` accepte un mot de passe en clair ou un hash deja calcule.

    Si la valeur commence par `$2` (bcrypt), on l utilise tel quel ; sinon on la
    hashe d abord. Permet aux appelants DB et memoire de partager le meme
    payload (`password_hash`) sans se coordonner.
    """
    email_l = email.lower()
    if email_l in _store.users_by_email:
        raise ValueError("email deja utilise")
    uid = str(uuid.uuid4())
    if isinstance(password, str) and password.startswith("$2"):
        password_hash = password
    else:
        password_hash = _hash(password)
    row = _UserRow({
        "user_id": uid,
        "email": email_l,
        "password_hash": password_hash,
        "display_name": display_name or email_l.split("@")[0],
        "is_active": True,
        "created_at": _now(),
    })
    _store.users[uid] = row
    _store.users_by_email[email_l] = uid
    return row


async def verify_user_credentials(email: str, password: str) -> dict | None:
    """Retourne la row user si ok, sinon None."""
    row = await get_user_by_email(email)
    if row is None:
        return None
    if not _verify(password, row["password_hash"]):
        return None
    return row


# ---------------------------------------------------------------------------
# Memberships
# ---------------------------------------------------------------------------

async def add_membership(user_id: str, org_id: str, role: str) -> dict:
    row = _MembershipRow({"user_id": user_id, "org_id": org_id, "role": role})
    _store.memberships.append(row)
    return row


async def get_memberships(user_id: str) -> list[dict]:
    return [m for m in _store.memberships if m["user_id"] == user_id]


async def get_first_membership(user_id: str) -> dict | None:
    ms = await get_memberships(user_id)
    return ms[0] if ms else None


# ---------------------------------------------------------------------------
# Refresh tokens
# ---------------------------------------------------------------------------

async def store_refresh_token(jti: str, user_id: str, expires_at: datetime) -> None:
    _store.refresh_tokens[jti] = _RefreshTokenRow({
        "jti": jti, "user_id": user_id, "expires_at": expires_at,
        "revoked_at": None,
        "token_hash": None,
        "org_id": None,
    })


async def get_refresh_token(jti: str) -> dict | None:
    return _store.refresh_tokens.get(jti)


async def revoke_refresh_token(jti: str) -> None:
    if jti in _store.refresh_tokens:
        _store.refresh_tokens[jti]["revoked_at"] = _now()


# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------

async def create_api_key(user_id: str, key_hash: str, label: str = "") -> dict:
    kid = str(uuid.uuid4())
    row = {
        "key_id": kid, "user_id": user_id, "key_hash": key_hash, "label": label,
        "created_at": _now(),
    }
    _store.api_keys[kid] = row
    return row


async def get_api_key(key_hash: str) -> dict | None:
    for row in _store.api_keys.values():
        if row["key_hash"] == key_hash:
            return row
    return None
