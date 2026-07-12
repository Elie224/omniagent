"""Store d idempotence (SQL via SQLAlchemy, multi-instance).

Concurrence : on s appuie sur la cle primaire `key` (UPSERT via INSERT ... ON CONFLICT).
L expiration est geree par `cleanup_expired()` (a appeler via un job ou un GC).
"""
from __future__ import annotations
import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import select, delete, and_

from omniagent.core.models.db import IdempotencyKeyRow


class IdempotencyConflictError(Exception):
    """Levee si une requete reutilise une cle avec un body different."""


@dataclass
class IdempotencyRecord:
    key: str
    request_hash: str
    status_code: int
    body: Any
    tenant_id: str = "default"
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0

    def is_expired(self, now: float | None = None) -> bool:
        if self.expires_at <= 0:
            return False
        return (now or time.time()) > self.expires_at


def hash_request(method: str, path: str, body: Any) -> str:
    """Hash deterministe d une requete (methode + path + body JSON)."""
    try:
        body_str = json.dumps(body, sort_keys=True, default=str)
    except (TypeError, ValueError):
        body_str = str(body)
    payload = method + "\\n" + path + "\\n" + body_str
    return hashlib.sha256(payload.encode()).hexdigest()


class IdempotencyStore(ABC):
    @abstractmethod
    def get(self, key: str, tenant_id: str = "default") -> Optional[IdempotencyRecord]: ...
    @abstractmethod
    def put(self, record: IdempotencyRecord) -> None: ...
    @abstractmethod
    def delete(self, key: str, tenant_id: str = "default") -> None: ...
    @abstractmethod
    def cleanup_expired(self) -> int: ...


class InMemoryIdempotencyStore(IdempotencyStore):
    """Fallback in-memory (1 seule instance)."""

    def __init__(self, default_ttl_s: int = 24 * 3600):
        self._store: dict[tuple[str, str], IdempotencyRecord] = {}
        self._default_ttl = default_ttl_s

    def get(self, key, tenant_id="default"):
        rec = self._store.get((tenant_id, key))
        if rec is None or rec.is_expired():
            return None
        return rec

    def put(self, record):
        self._store[(record.tenant_id, record.key)] = record

    def delete(self, key, tenant_id="default"):
        self._store.pop((tenant_id, key), None)

    def cleanup_expired(self) -> int:
        expired = [k for k, v in self._store.items() if v.is_expired()]
        for k in expired:
            del self._store[k]
        return len(expired)

    def __len__(self) -> int:
        return len(self._store)


class SqlIdempotencyStore(IdempotencyStore):
    """Store SQL (async, via SQLAlchemy). Recommande pour multi-instance."""

    def __init__(self, db_session, default_ttl_s: int = 24 * 3600):
        self._db = db_session
        self._default_ttl = default_ttl_s

    def get(self, key, tenant_id="default"):
        # Note: SQLAlchemy async -> on doit etre dans une event loop.
        # Pour rester sync a l appel, on lance une coroutine via asyncio.
        import asyncio
        try:
            asyncio.get_running_loop()
            # deja dans une loop -> delegue a l appelant
            raise RuntimeError(
                "SqlIdempotencyStore.get doit etre appele via aget() dans un contexte async"
            )
        except RuntimeError as e:
            if "no running event loop" not in str(e):
                raise
            return asyncio.run(self._aget(key, tenant_id))

    async def aget(self, key: str, tenant_id: str = "default") -> Optional[IdempotencyRecord]:
        async with self._db() as s:
            r = await s.execute(
                select(IdempotencyKeyRow).where(
                    and_(
                        IdempotencyKeyRow.key == key,
                        IdempotencyKeyRow.tenant_id == tenant_id,
                    )
                )
            )
            row = r.scalar_one_or_none()
            if row is None:
                return None
            from datetime import datetime, timezone
            if row.expires_at and row.expires_at < datetime.now(timezone.utc):
                # Expired -> supprimer
                await s.execute(
                    delete(IdempotencyKeyRow).where(
                        and_(
                            IdempotencyKeyRow.key == key,
                            IdempotencyKeyRow.tenant_id == tenant_id,
                        )
                    )
                )
                await s.commit()
                return None
            return IdempotencyRecord(
                key=row.key, request_hash=row.request_hash,
                status_code=row.status_code, body=row.body,
                tenant_id=row.tenant_id, created_at=row.created_at.timestamp(),
                expires_at=row.expires_at.timestamp(),
            )

    def put(self, record: IdempotencyRecord) -> None:
        import asyncio
        try:
            asyncio.get_running_loop()
            raise RuntimeError("SqlIdempotencyStore.put doit etre appele via aput() en contexte async")
        except RuntimeError as e:
            if "no running event loop" not in str(e):
                raise
            asyncio.run(self._aput(record))

    async def _aput(self, record: IdempotencyRecord) -> None:
        from datetime import datetime, timezone, timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self._default_ttl) if record.expires_at <= 0 \
            else datetime.fromtimestamp(record.expires_at, tz=timezone.utc)
        async with self._db() as s:
            existing = await s.execute(
                select(IdempotencyKeyRow).where(
                    and_(
                        IdempotencyKeyRow.key == record.key,
                        IdempotencyKeyRow.tenant_id == record.tenant_id,
                    )
                )
            )
            row = existing.scalar_one_or_none()
            if row is None:
                s.add(IdempotencyKeyRow(
                    key=record.key, tenant_id=record.tenant_id,
                    request_hash=record.request_hash,
                    status_code=record.status_code, body=record.body,
                    expires_at=expires_at,
                ))
            else:
                row.request_hash = record.request_hash
                row.status_code = record.status_code
                row.body = record.body
                row.expires_at = expires_at
            await s.commit()

    def delete(self, key, tenant_id="default"):
        import asyncio
        try:
            asyncio.get_running_loop()
            raise RuntimeError("SqlIdempotencyStore.delete doit etre appele via adelete() en contexte async")
        except RuntimeError as e:
            if "no running event loop" not in str(e):
                raise
            asyncio.run(self._adelete(key, tenant_id))

    async def _adelete(self, key: str, tenant_id: str) -> None:
        async with self._db() as s:
            await s.execute(
                delete(IdempotencyKeyRow).where(
                    and_(
                        IdempotencyKeyRow.key == key,
                        IdempotencyKeyRow.tenant_id == tenant_id,
                    )
                )
            )
            await s.commit()

    def cleanup_expired(self) -> int:
        import asyncio
        from datetime import datetime, timezone
        try:
            asyncio.get_running_loop()
            raise RuntimeError("cleanup_expired doit etre appele dans un contexte async")
        except RuntimeError as e:
            if "no running event loop" not in str(e):
                raise
            return asyncio.run(self._acleanup())

    async def _acleanup(self) -> int:
        from datetime import datetime, timezone
        async with self._db() as s:
            r = await s.execute(
                delete(IdempotencyKeyRow).where(
                    IdempotencyKeyRow.expires_at < datetime.now(timezone.utc)
                )
            )
            await s.commit()
            return r.rowcount or 0
