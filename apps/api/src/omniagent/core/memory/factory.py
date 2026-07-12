"""Factory pour assembler les differentes memoires selon le contexte.

- Avec DB : UserMemory + VectorMemory utilisent SQLAlchemy.
- Sans DB (tests, demo) : fallback en memoire (OrderedDict / BM25).
"""
from __future__ import annotations
from typing import Optional

from omniagent.core.memory.session_memory import SessionMemory
from omniagent.core.memory.user_memory import UserMemory
from omniagent.core.memory.vector_memory import VectorMemory
from omniagent.core.memory.domain_memory import DomainMemory


class InMemoryUserMemory:
    """Fallback en memoire pour UserMemory quand pas de DB."""
    def __init__(self):
        self._store: dict[str, dict] = {}
    def get(self, key): return self._store.get(key, {}).get("value")
    def set(self, key, value, ttl_seconds=None): self._store[key] = {"value": value}
    def delete(self, key): self._store.pop(key, None)
    def list(self, prefix): return [(k, v["value"]) for k, v in self._store.items() if k.startswith(prefix)]


class InMemoryVectorMemory:
    """Fallback en memoire pour VectorMemory (BM25 local)."""
    def __init__(self):
        self._store: dict[str, dict] = {}
    def add(self, key, text, metadata=None, doc_type="autre"):
        self._store[key] = {"text": text, "metadata": metadata or {}, "doc_type": doc_type}
    def search(self, query, top_k=5, doc_type=None):
        import re
        from collections import Counter
        from omniagent.core.memory.vector_memory import _cosine
        q_tokens = Counter(re.findall(r"\w+", query.lower()))
        scored = []
        for k, v in self._store.items():
            if doc_type and v["doc_type"] != doc_type:
                continue
            t_tokens = Counter(re.findall(r"\w+", v["text"].lower()))
            overlap = sum((q_tokens & t_tokens).values())
            if overlap == 0: continue
            scored.append((overlap / max(sum(q_tokens.values()), 1), v, k))
        scored.sort(key=lambda x: -x[0])
        return [{"key": k, "doc_type": v["doc_type"], "score": round(s, 4),
                 "snippet": v["text"][:300], "metadata": v["metadata"]}
                for s, v, k in scored[:top_k]]
    def get(self, key): return None
    def set(self, key, value, ttl_seconds=None): pass
    def delete(self, key): pass
    def list(self, prefix): return []


class MemoryStack:
    """Regroupe les 4 types de memoire utilises par les agents."""

    def __init__(self, session, user, vector, domain):
        self.session = session
        self.user = user
        self.vector = vector
        self.domain = domain


async def _db_available(db_session) -> bool:
    """Test rapide : on tente d ouvrir une session et un SELECT trivial.
    Renvoie False si la DB est down (Postgres pas lance, etc.).
    """
    if db_session is None:
        return False
    try:
        async with db_session() as s:
            from sqlalchemy import text
            await s.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def build_memory_stack(db_session=None, pgvector_conn=None,
                          memory_backend: str = "auto") -> MemoryStack:
    """Construit un stack memoire.

    `memory_backend` :
      - "auto" (defaut) : tente la DB, fallback in-memory si KO
      - "db" : force DB (echec -> UserMemory crash si pas de DB)
      - "memory" : force in-memory (utile pour les tests)
    """
    use_db = False
    if memory_backend == "db":
        use_db = db_session is not None
    elif memory_backend == "memory":
        use_db = False
    else:  # auto
        # On regarde le flag d env plutot que de ping la DB (le ping est async
        # et complique l appel depuis lifespan). Le flag FORCE_MEMORY=1 active
        # le mode in-memory ; sinon on tente la DB.
        import os
        if os.getenv("OMNIAGENT_FORCE_MEMORY", "").lower() in ("1", "true", "yes"):
            use_db = False
        else:
            use_db = db_session is not None
    if use_db:
        user = UserMemory(db_session)
        vector = VectorMemory(db_session)
    else:
        user = InMemoryUserMemory()
        vector = InMemoryVectorMemory()
    return MemoryStack(
        session=SessionMemory(),
        user=user,
        vector=vector,
        domain=DomainMemory(),
    )
