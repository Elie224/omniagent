"""EventStore : persistance append-only des evenements metier.

Objectif : remplacer l historique in-memory du bus par un store queryable
qui survit au restart du process. Deux backends :

- `InMemoryEventStore` (defaut) : append + query en RAM, perte au restart.
  Conserve la semantique actuelle de l EventBus.
- `SqliteEventStore` : persistance via aiosqlite. Append-only (pas d update,
  pas de delete) pour preserver l integrite du journal.

L interface est minimale (append + query) pour rester compatible avec le bus
existant et eviter de coupler les producteurs d events a un schema DB.
"""
from __future__ import annotations
import asyncio
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .bus import Event


@dataclass
class StoredEvent:
    """Vue normalisee d un event tel que stocke."""
    event_id: str
    type: str
    source: str
    timestamp: str
    payload: dict
    correlation_id: str | None
    causation_id: str | None
    user_id: str | None
    tenant_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "type": self.type,
            "source": self.source,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
        }


class EventStore(Protocol):
    """Interface minimale d un store d evenements append-only."""

    async def append(self, event: Event, tenant_id: str | None = None) -> None:
        ...

    async def query(
        self,
        event_type: str | None = None,
        user_id: str | None = None,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[StoredEvent]:
        ...

    async def close(self) -> None:
        ...


def _to_stored(event: Event, tenant_id: str | None = None) -> StoredEvent:
    return StoredEvent(
        event_id=event.event_id,
        type=event.type.value,
        source=event.source,
        timestamp=event.timestamp.isoformat(),
        payload=event.payload,
        correlation_id=event.correlation_id,
        causation_id=event.causation_id,
        user_id=event.user_id,
        tenant_id=tenant_id,
    )


class InMemoryEventStore:
    """Store en RAM, perte au restart. Conservé pour la parité fonctionnelle."""

    def __init__(self, history_limit: int = 1000):
        self._events: list[StoredEvent] = []
        self._history_limit = history_limit
        self._lock = asyncio.Lock()

    async def append(self, event: Event, tenant_id: str | None = None) -> None:
        async with self._lock:
            self._events.append(_to_stored(event, tenant_id))
            if len(self._events) > self._history_limit:
                self._events.pop(0)

    async def query(
        self,
        event_type: str | None = None,
        user_id: str | None = None,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[StoredEvent]:
        results: list[StoredEvent] = []
        for ev in self._events:
            if event_type and ev.type != event_type:
                continue
            if user_id and ev.user_id != user_id:
                continue
            if tenant_id and ev.tenant_id != tenant_id:
                continue
            if correlation_id and ev.correlation_id != correlation_id:
                continue
            if since and datetime.fromisoformat(ev.timestamp) < since:
                continue
            results.append(ev)
            if len(results) >= limit:
                break
        return results

    async def close(self) -> None:
        self._events.clear()


class SqliteEventStore:
    """Store SQLite append-only via aiosqlite (synchrone wrappé en to_thread).

    Schema :
        events (
            event_id       TEXT PRIMARY KEY,
            type           TEXT NOT NULL,
            source         TEXT NOT NULL,
            timestamp      TEXT NOT NULL,
            payload_json   TEXT NOT NULL,
            correlation_id TEXT,
            causation_id   TEXT,
            user_id        TEXT,
            tenant_id      TEXT
        )

    Index : (type, user_id, tenant_id, timestamp) pour query rapides.
    Append-only garanti par le code (aucun UPDATE/DELETE exposé).
    """

    def __init__(self, db_path: str | Path):
        self._db_path = str(db_path)
        self._lock = asyncio.Lock()
        # Initialisation synchrone (chemin fiable, pas de race au startup)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id       TEXT PRIMARY KEY,
                    type           TEXT NOT NULL,
                    source         TEXT NOT NULL,
                    timestamp      TEXT NOT NULL,
                    payload_json   TEXT NOT NULL,
                    correlation_id TEXT,
                    causation_id   TEXT,
                    user_id        TEXT,
                    tenant_id      TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_tenant ON events(tenant_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_corr ON events(correlation_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(timestamp)")
            conn.commit()

    async def append(self, event: Event, tenant_id: str | None = None) -> None:
        stored = _to_stored(event, tenant_id)
        payload_json = json.dumps(stored.payload, default=str, ensure_ascii=False)
        async with self._lock:
            await asyncio.to_thread(self._append_sync, stored, payload_json)

    def _append_sync(self, stored: StoredEvent, payload_json: str) -> None:
        with sqlite3.connect(self._db_path) as conn:
            # INSERT OR IGNORE : idempotence sur event_id (replay-safe)
            conn.execute(
                """
                INSERT OR IGNORE INTO events
                  (event_id, type, source, timestamp, payload_json,
                   correlation_id, causation_id, user_id, tenant_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stored.event_id, stored.type, stored.source,
                    stored.timestamp, payload_json,
                    stored.correlation_id, stored.causation_id,
                    stored.user_id, stored.tenant_id,
                ),
            )
            conn.commit()

    async def query(
        self,
        event_type: str | None = None,
        user_id: str | None = None,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[StoredEvent]:
        clauses: list[str] = []
        params: list[Any] = []
        if event_type:
            clauses.append("type = ?")
            params.append(event_type)
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        if tenant_id:
            clauses.append("tenant_id = ?")
            params.append(tenant_id)
        if correlation_id:
            clauses.append("correlation_id = ?")
            params.append(correlation_id)
        if since:
            clauses.append("timestamp >= ?")
            params.append(since.isoformat())
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        sql = (
            "SELECT event_id, type, source, timestamp, payload_json, "
            "correlation_id, causation_id, user_id, tenant_id "
            f"FROM events{where} ORDER BY timestamp ASC LIMIT ?"
        )
        rows = await asyncio.to_thread(self._query_sync, sql, params)
        return [self._row_to_stored(r) for r in rows]

    def _query_sync(self, sql: str, params: list[Any]) -> list[tuple]:
        with sqlite3.connect(self._db_path) as conn:
            cur = conn.execute(sql, params)
            return cur.fetchall()

    def _row_to_stored(self, row: tuple) -> StoredEvent:
        return StoredEvent(
            event_id=row[0], type=row[1], source=row[2],
            timestamp=row[3], payload=json.loads(row[4]),
            correlation_id=row[5], causation_id=row[6],
            user_id=row[7], tenant_id=row[8],
        )

    async def close(self) -> None:
        # SQLite : pas de pool a fermer, on no-op
        return None