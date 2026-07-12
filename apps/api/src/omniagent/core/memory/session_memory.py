"""Memoire de session (duree d''un agent_run)."""
from datetime import datetime, timedelta, timezone
from collections import OrderedDict
from threading import RLock


class SessionMemory:
    """Stocke le contexte d''une execution d''agent (utilise OrderedDict + TTL)."""

    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self._store: OrderedDict[str, tuple[datetime, object]] = OrderedDict()
        self._max_size = max_size
        self._ttl = default_ttl
        self._lock = RLock()

    def get(self, key: str) -> object | None:
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            ts, value = entry
            if datetime.now(timezone.utc) - ts > timedelta(seconds=self._ttl):
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: object, ttl_seconds: int | None = None) -> None:
        with self._lock:
            if len(self._store) >= self._max_size:
                self._store.popitem(last=False)
            self._store[key] = (datetime.now(timezone.utc), value)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
