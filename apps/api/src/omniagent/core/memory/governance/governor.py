"""Gouvernance memoire : TTL, ranking, protection anti-poisoning.

Le memory poisoning designe les attaques ou un utilisateur (ou un input indirect)
injecte du contenu malicieux dans la memoire d un agent pour le detourner.
"""
from __future__ import annotations
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from threading import RLock


class MemoryTrust(str, Enum):
    SYSTEM = "system"          # source sure (orchestrateur)
    USER = "user"              # input utilisateur
    EXTERNAL = "external"      # scrape web, API tierce
    UNKNOWN = "unknown"


# Patterns d injection classiques
INJECTION_PATTERNS = [
    r"ignore (all|the) previous instructions",
    r"oublie toutes les instructions",
    r"disregard your prior",
    r"you are now",
    r"tu es maintenant",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"system:\s*",
    r"assistant:\s*",
    r"^\s*##\s*new instructions",
    r"act as",
    r"pretend to be",
    r"do anything now",
]


@dataclass
class MemoryEntry:
    key: str
    value: object
    trust: MemoryTrust
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ttl_seconds: int | None = None
    importance: float = 0.5     # 0..1
    reliability: float = 0.8    # 0..1 (estimee par le systeme)
    access_count: int = 0
    last_accessed: datetime | None = None
    source: str = "unknown"

    def is_expired(self, now: datetime | None = None) -> bool:
        if self.ttl_seconds is None:
            return False
        now = now or datetime.now(timezone.utc)
        return (now - self.created_at) > timedelta(seconds=self.ttl_seconds)

    @property
    def rank(self) -> float:
        """Score composite : importance x fiabilite x recence x popularite."""
        recency = 1.0
        if self.last_accessed:
            age_h = (datetime.now(timezone.utc) - self.last_accessed).total_seconds() / 3600
            recency = max(0.1, 1.0 - age_h / 168)  # decroissance sur 1 semaine
        popularity = min(1.0, 0.5 + self.access_count * 0.05)
        return self.importance * self.reliability * recency * popularity


class MemoryGovernor:
    """Gere la memoire avec TTL, ranking et detection d injection."""

    def __init__(self):
        self._store: dict[str, MemoryEntry] = {}
        self._lock = RLock()
        self._quarantined: list[MemoryEntry] = []  # entries suspectes

    def put(self, key: str, value: object, trust: MemoryTrust = MemoryTrust.USER,
            ttl_seconds: int | None = None, importance: float = 0.5,
            source: str = "unknown") -> dict:
        # Detection d injection pour les entrees non-systeme
        is_safe, reason = self._check_injection(value, trust)
        if not is_safe:
            entry = MemoryEntry(key, value, trust, importance=0.0, reliability=0.0, source=source)
            self._quarantined.append(entry)
            return {"stored": False, "quarantined": True, "reason": reason}
        with self._lock:
            self._store[key] = MemoryEntry(key, value, trust, ttl_seconds=ttl_seconds,
                                            importance=importance, source=source)
        return {"stored": True, "key": key}

    def get(self, key: str) -> object | None:
        with self._lock:
            entry = self._store.get(key)
            if not entry or entry.is_expired():
                if entry and entry.is_expired():
                    del self._store[key]
                return None
            entry.access_count += 1
            entry.last_accessed = datetime.now(timezone.utc)
            return entry.value

    def get_ranked(self, prefix: str, top_k: int = 10) -> list[tuple[str, object, float]]:
        with self._lock:
            # Nettoyage des expires
            expired = [k for k, v in self._store.items() if v.is_expired()]
            for k in expired:
                del self._store[k]
            candidates = [(k, v) for k, v in self._store.items() if k.startswith(prefix)]
        return sorted(((k, v.value, v.rank) for k, v in candidates),
                       key=lambda x: -x[2])[:top_k]

    def evict_to(self, max_size: int) -> int:
        """Evince les entrees les moins importantes si on depasse max_size."""
        with self._lock:
            if len(self._store) <= max_size:
                return 0
            ranked = sorted(self._store.items(), key=lambda kv: kv[1].rank)
            to_remove = len(self._store) - max_size
            for k, _ in ranked[:to_remove]:
                del self._store[k]
            return to_remove

    def _check_injection(self, value: object, trust: MemoryTrust) -> tuple[bool, str]:
        if trust == MemoryTrust.SYSTEM:
            return True, ""
        text = str(value) if not isinstance(value, str) else value
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
                return False, f"Pattern d injection detecte: {pattern}"
        return True, ""

    def stats(self) -> dict:
        with self._lock:
            return {
                "total": len(self._store),
                "quarantined": len(self._quarantined),
                "by_trust": {
                    t.value: sum(1 for v in self._store.values() if v.trust == t)
                    for t in MemoryTrust
                },
            }


memory_governor = MemoryGovernor()
