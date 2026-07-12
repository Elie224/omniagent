"""Memoire vectorielle (pgvector en prod, fallback BM25 local sinon).

- `add(key, text, metadata)` : stocke le texte + embedding (ou juste le texte)
- `search(query, top_k)` : retrouve les documents les plus similaires
   - Si l embedding est disponible : cosine similarity
   - Sinon : BM25 (overlap de tokens, comme dans KnowledgeAgent)
"""
from __future__ import annotations
import math
import re
from collections import Counter
from typing import Any
from sqlalchemy import select, delete

from omniagent.core.memory.base import MemoryBackend
from omniagent.core.models.db import VectorMemoryRow


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class VectorMemory(MemoryBackend):
    """Stocke et retrouve des documents par similarite (embeddings + fallback BM25)."""

    def __init__(self, db_session, embed_fn=None):
        self._db = db_session
        self._embed_fn = embed_fn  # callable(text) -> list[float] (defaut: None = BM25)
        self._user: str = "demo"
        self._tenant: str = "default"

    # --- scope tenant (defense en profondeur, appele par TenantScopeMiddleware) ---
    def set_scope(self, user_id: str, tenant_id: str) -> None:
        self._user = user_id
        self._tenant = tenant_id

    def _tenant_filter(self):
        """Filtre tenant obligatoire. Empeche les requetes sans scope."""
        if not self._tenant:
            raise RuntimeError(
                "VectorMemory utilise sans tenant scope. "
                "Appeler set_scope(user_id, tenant_id) d abord "
                "(automatiquement par TenantScopeMiddleware)."
            )
        return VectorMemoryRow.tenant_id == self._tenant

    # --- API metier (async) ---
    async def add(self, key: str, text: str, metadata: dict | None = None,
                   doc_type: str = "autre") -> None:
        embedding = []
        if self._embed_fn is not None:
            try:
                embedding = self._embed_fn(text)
            except Exception:
                embedding = []
        async with self._db() as s:
            existing = await s.execute(
                select(VectorMemoryRow).where(VectorMemoryRow.key == key)
            )
            row = existing.scalar_one_or_none()
            if row is None:
                s.add(VectorMemoryRow(
                    key=key, doc_type=doc_type, text=text,
                    metadata_=metadata or {}, embedding=embedding,
                ))
            else:
                row.text = text
                row.metadata_ = metadata or {}
                row.embedding = embedding
                row.doc_type = doc_type
            await s.commit()

    async def search(self, query: str, top_k: int = 5,
                      doc_type: str | None = None,
                      tenant_id: str | None = None) -> list[dict]:
        """Recherche semantique scopee par tenant. Embedding si dispo, sinon BM25."""
        tid = tenant_id or self._tenant
        if not tid:
            raise RuntimeError("VectorMemory.search sans tenant scope")
        async with self._db() as s:
            stmt = select(VectorMemoryRow).where(
                VectorMemoryRow.tenant_id == tid
            )
            if doc_type:
                stmt = stmt.where(VectorMemoryRow.doc_type == doc_type)
            rows = (await s.execute(stmt)).scalars().all()
        if not rows:
            return []
        if self._embed_fn is not None:
            q_vec = self._embed_fn(query)
            scored = [(_cosine(q_vec, list(r.embedding or [])), r) for r in rows]
        else:
            q_tokens = Counter(_tokenize(query))
            scored = []
            for r in rows:
                r_tokens = Counter(_tokenize(r.text))
                overlap = sum((q_tokens & r_tokens).values())
                if overlap == 0:
                    continue
                # Score BM25 simplifie
                tf = 1 + math.log(1 + overlap)
                idf = math.log((len(rows) + 1) / (1 + sum(1 for x in rows if x is not r)))
                scored.append((tf * idf, r))
        scored.sort(key=lambda x: -x[0])
        return [
            {"key": r.key, "doc_type": r.doc_type, "score": round(float(s), 4),
             "snippet": r.text[:300], "metadata": r.metadata_}
            for s, r in scored[:top_k] if s > 0
        ]

    # --- MemoryBackend (sync) : delegue a un fallback en memoire (no-op en pratique) ---
    def get(self, key: str) -> Any | None: return None
    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None: pass
    def delete(self, key: str) -> None: pass
    def list(self, prefix: str) -> list[tuple[str, Any]]: return []