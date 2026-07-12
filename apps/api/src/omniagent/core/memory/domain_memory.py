"""Memoire metier : regles sectorielles, blacklist opt-in, RGPD exclusions."""
from datetime import datetime, timedelta, timezone

from omniagent.core.memory.base import MemoryBackend


class DomainMemory(MemoryBackend):
    """Memoire partagee entre modules : qui est candidat, qui est debiteur, exclusions."""

    def __init__(self):
        self._store: dict[str, dict] = {}

    def add_exclusion(self, contact_id: str, reason: str, ttl_days: int = 90) -> None:
        self._store[f"excl:{contact_id}"] = {
            "reason": reason,
            "expires_at": datetime.now(timezone.utc) + timedelta(days=ttl_days),
        }

    def is_excluded(self, contact_id: str, reason: str | None = None) -> bool:
        entry = self._store.get(f"excl:{contact_id}")
        if not entry:
            return False
        if entry["expires_at"] < datetime.now(timezone.utc):
            self._store.pop(f"excl:{contact_id}", None)
            return False
        if reason and entry["reason"] != reason:
            return False
        return True

    def get(self, key: str) -> object | None:
        return self._store.get(key)

    def set(self, key: str, value: object, ttl_seconds: int | None = None) -> None:
        self._store[key] = value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def list(self, prefix: str) -> list[tuple[str, object]]:
        return [(k, v) for k, v in self._store.items() if k.startswith(prefix)]