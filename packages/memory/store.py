"""Store memoire partagee entre modules (version in-memory, a remplacer par PostgreSQL+pgvector)."""
from datetime import datetime, timedelta


class SharedMemory:
    """Permet aux modules de partager des infos (qui est candidat, qui est debiteur, etc.)."""

    def __init__(self):
        self._exclusions: list[dict] = []

    def add_exclusion(self, contact_id: str, reason: str, ttl_days: int = 90) -> None:
        self._exclusions.append({
            "contact_id": contact_id,
            "reason": reason,
            "expires_at": datetime.utcnow() + timedelta(days=ttl_days),
        })

    def is_excluded(self, contact_id: str, reason: str | None = None) -> bool:
        now = datetime.utcnow()
        for e in self._exclusions:
            if e["contact_id"] != contact_id:
                continue
            if e["expires_at"] < now:
                continue
            if reason and e["reason"] != reason:
                continue
            return True
        return False