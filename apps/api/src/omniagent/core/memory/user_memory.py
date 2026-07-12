"""Memoire utilisateur persistante (profil, preferences, historique).

Stocke en base via SQLAlchemy. Scope = (tenant_id, user_id, key).
"""
from __future__ import annotations
from typing import Any
from sqlalchemy import select, delete

from omniagent.core.memory.base import MemoryBackend
from omniagent.core.models.db import UserMemoryRow


class UserMemory(MemoryBackend):
    """Wrapper sur la table user_memory (scope tenant + user)."""

    def __init__(self, db_session, default_user_id: str = "demo",
                  default_tenant_id: str = "default"):
        self._db = db_session
        self._user = default_user_id
        self._tenant = default_tenant_id

    def set_scope(self, user_id: str, tenant_id: str) -> None:
        """Met a jour le scope par defaut (appele par le middleware tenant)."""
        self._user = user_id
        self._tenant = tenant_id

    # --- API sync (MemoryBackend) : fallback in-memory (no-op en pratique) ---
    def get(self, key: str) -> Any | None: return None
    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None: pass
    def delete(self, key: str) -> None: pass
    def list(self, prefix: str) -> list[tuple[str, Any]]: return []

    # --- API async scopee ---
    async def aget(self, key: str, user_id: str | None = None,
                     tenant_id: str | None = None) -> Any | None:
        uid = user_id or self._user
        tid = tenant_id or self._tenant
        try:
            async with self._db() as s:
                r = await s.execute(
                    select(UserMemoryRow).where(
                        UserMemoryRow.tenant_id == tid,
                        UserMemoryRow.user_id == uid,
                        UserMemoryRow.key == key,
                    )
                )
                row = r.scalar_one_or_none()
                return row.value if row else None
        except Exception:
            # DB indisponible (dev sans Postgres) -> vide.
            return None

    async def aset(self, key: str, value: Any,
                    ttl_seconds: int | None = None,
                    user_id: str | None = None,
                    tenant_id: str | None = None) -> None:
        uid = user_id or self._user
        tid = tenant_id or self._tenant
        try:
            async with self._db() as s:
                r = await s.execute(
                    select(UserMemoryRow).where(
                        UserMemoryRow.tenant_id == tid,
                        UserMemoryRow.user_id == uid,
                        UserMemoryRow.key == key,
                    )
                )
                row = r.scalar_one_or_none()
                if row is None:
                    s.add(UserMemoryRow(tenant_id=tid, user_id=uid, key=key, value=value))
                else:
                    row.value = value
                await s.commit()
        except Exception:
            # DB indisponible -> silent no-op (best-effort en dev).
            return

    async def adelete(self, key: str, user_id: str | None = None,
                        tenant_id: str | None = None) -> None:
        uid = user_id or self._user
        tid = tenant_id or self._tenant
        try:
            async with self._db() as s:
                await s.execute(
                    delete(UserMemoryRow).where(
                        UserMemoryRow.tenant_id == tid,
                        UserMemoryRow.user_id == uid,
                        UserMemoryRow.key == key,
                    )
                )
                await s.commit()
        except Exception:
            return

    async def alist(self, prefix: str, user_id: str | None = None,
                      tenant_id: str | None = None) -> list[tuple[str, Any]]:
        uid = user_id or self._user
        tid = tenant_id or self._tenant
        async with self._db() as s:
            r = await s.execute(
                select(UserMemoryRow).where(
                    UserMemoryRow.tenant_id == tid,
                    UserMemoryRow.user_id == uid,
                    UserMemoryRow.key.like(prefix + "%"),
                )
            )
            return [(row.key, row.value) for row in r.scalars()]
