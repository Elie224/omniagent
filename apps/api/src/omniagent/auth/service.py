"""Service auth : hash mots de passe, JWT, refresh, rotation.

Conventions :
- Mots de passe : bcrypt (passlib) ou argon2 si dispo
- Access token : JWT signe, 15 min, contient user_id + org_id + role
- Refresh token : JWT signe, 7 jours, stocke en base (hash) pour revocation
- Rotation : un nouveau refresh est emis a chaque utilisation, l ancien est revoque
- En cas de vol : table refresh_tokens -> revocation immediate
"""
from __future__ import annotations
import hashlib
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from jose import JWTError, jwt
import bcrypt

from omniagent.core.config import settings


# --- Hash de mot de passe (bcrypt direct, passlib est casse avec bcrypt 4+) ---
def hash_password(password: str) -> str:
    """Hash bcrypt. Limite a 72 bytes par design bcrypt (on tronque)."""
    if not isinstance(password, str) or len(password) < 8:
        raise ValueError("Password doit faire au moins 8 caracteres")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password[:72].encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password[:72].encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


# --- JWT ---
def _secret() -> str:
    return settings.jwt_secret or settings.secret_key


def create_access_token(user_id: str, org_id: str, role: str,
                         extra: dict | None = None,
                         ttl_s: int | None = None) -> tuple[str, int]:
    """Cree un access token JWT. Retourne (token, expires_in_seconds)."""
    now = datetime.now(timezone.utc)
    ttl = ttl_s or settings.access_token_ttl_s
    payload = {
        "sub": user_id,
        "org_id": org_id,
        "role": role,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, _secret(), algorithm=settings.jwt_algorithm)
    return token, ttl


def create_refresh_token(user_id: str, org_id: str) -> tuple[str, str, datetime]:
    """Cree un refresh token. Retourne (token, token_id, expires_at)."""
    now = datetime.now(timezone.utc)
    token_id = str(uuid.uuid4())
    ttl = settings.refresh_token_ttl_s
    payload = {
        "sub": user_id,
        "org_id": org_id,
        "type": "refresh",
        "jti": token_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
    }
    token = jwt.encode(payload, _secret(), algorithm=settings.jwt_algorithm)
    return token, token_id, now + timedelta(seconds=ttl)


def decode_token(token: str, expected_type: str | None = None) -> dict:
    """Decode un JWT et verifie la signature/expiration/type.

    Leve `InvalidTokenError` si invalide.
    """
    try:
        payload = jwt.decode(token, _secret(), algorithms=[settings.jwt_algorithm])
    except JWTError as e:
        raise InvalidTokenError(f"JWT invalide: {e}") from e
    if expected_type and payload.get("type") != expected_type:
        raise InvalidTokenError(
            f"Type de token attendu {expected_type!r}, recu {payload.get('type')!r}"
        )
    if "exp" in payload and datetime.now(timezone.utc).timestamp() > payload["exp"]:
        raise InvalidTokenError("Token expire")
    return payload


# --- Helpers ---
def hash_refresh_token(token: str) -> str:
    """Hash SHA-256 (cote DB, on ne stocke jamais le token en clair)."""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_api_key() -> tuple[str, str]:
    """Genere une cle d API. Retourne (key_id, secret). Le secret est affiche
    une seule fois a la creation, on ne stocke que son hash."""
    key_id = "ak_" + secrets.token_urlsafe(16)
    secret = secrets.token_urlsafe(32)
    return key_id, secret


def hash_api_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


# --- Erreurs ---
class InvalidTokenError(Exception):
    pass


class AuthError(Exception):
    """Erreur auth generique (mauvais password, user inactif, etc.)."""
    def __init__(self, message: str, code: str = "auth_error"):
        super().__init__(message)
        self.code = code
