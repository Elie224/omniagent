"""Chiffrement des donnees sensibles (CV, contacts, tokens)."""
import base64
import hashlib
import os

from cryptography.fernet import Fernet

from omniagent.core.config import settings


def _derive_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)


_fernet = Fernet(_derive_key(settings.secret_key))


def encrypt(value: str) -> str:
    return _fernet.encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet.decrypt(token.encode()).decode()


def hash_identifier(value: str) -> str:
    """Hash irreversible pour pseudonymisation (utile pour analytics)."""
    return hashlib.sha256(value.encode()).hexdigest()[:16]