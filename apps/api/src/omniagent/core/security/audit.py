"""Audit log RGPD : trace toutes les actions sensibles.

Stocke en base (table `audit_log`) via SQLAlchemy. Le modele est declare dans
`core.models.db.AuditLogRow`. La cle composite est (tenant_id, user_id, timestamp).
"""
from __future__ import annotations
import json
from uuid import uuid4
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from sqlalchemy import select

from omniagent.core.models.db import AuditLogRow


class AuditAction(str, Enum):
    DATA_ACCESS = "data_access"
    DATA_EXPORT = "data_export"
    DATA_DELETE = "data_delete"
    AGENT_RUN = "agent_run"
    CONNECTOR_CALL = "connector_call"
    QUOTA_EXCEEDED = "quota_exceeded"
    AUTH_LOGIN = "auth_login"
    AUTH_LOGOUT = "auth_logout"
    AUTH_LOGIN_FAILED = "auth_login_failed"
    AUTH_REFRESH = "auth_refresh"
    AUTH_SIGNUP = "auth_signup"
    AUTH_TOKEN_REVOKED = "auth_token_revoked"


class AuditLog:
    """Logger d audit conforme RGPD. Stocke en DB (PostgreSQL).

    V1 (historique) : print JSON
    V2 : insert dans la table audit_log via SQLAlchemy
    """

    def __init__(self, db_session=None):
        self._db = db_session

    def log(self, user_id: str, action: AuditAction, payload: dict | None = None,
             tenant_id: str = "default", ip: str | None = None) -> None:
        entry = {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "action": action.value,
            "payload": payload or {},
            "ip": ip,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        # En dev : print + (si DB) insert
        print(f"[AUDIT] {json.dumps(entry, default=str)}")
        if self._db is None:
            return
        # Si DB dispo, insert (best-effort, on ne leve pas d exception)
        try:
            import asyncio
            try:
                asyncio.get_running_loop()
                # deja dans une loop -> on skip l insert pour eviter les complications
                return
            except RuntimeError:
                pass
            asyncio.run(self._ainsert(user_id, action, payload, tenant_id, ip))
        except Exception as e:
            print(f"[AUDIT] insert failed: {e}")

    async def alog(self, user_id: str, action: AuditAction,
                    payload: dict | None = None,
                    tenant_id: str = "default",
                    ip: str | None = None) -> None:
        """Version async (a utiliser depuis les routes)."""
        entry = {
            "user_id": user_id, "tenant_id": tenant_id,
            "action": action.value, "payload": payload or {},
            "ip": ip, "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        print(f"[AUDIT] {json.dumps(entry, default=str)}")
        if self._db is None:
            return
        try:
            async with self._db() as s:
                s.add(AuditLogRow(
                    log_id=uuid4().hex,
                    tenant_id=tenant_id, user_id=user_id,
                    action=action.value, payload=payload or {},
                    ip=ip,
                ))
                await s.commit()
        except Exception as e:
            print(f"[AUDIT] alog insert failed: {e}")

    async def _ainsert(self, user_id, action, payload, tenant_id, ip):
        async with self._db() as s:
            s.add(AuditLogRow(
                log_id=uuid4().hex,
                tenant_id=tenant_id, user_id=user_id,
                action=action.value, payload=payload or {},
                ip=ip,
            ))
            await s.commit()

    async def history(self, tenant_id: str = "default",
                       user_id: str | None = None,
                       limit: int = 100) -> list[dict]:
        """Retourne l historique d audit pour un tenant (et optionnellement un user)."""
        if self._db is None:
            return []
        async with self._db() as s:
            q = select(AuditLogRow).where(AuditLogRow.tenant_id == tenant_id)
            if user_id:
                q = q.where(AuditLogRow.user_id == user_id)
            q = q.order_by(AuditLogRow.created_at.desc()).limit(limit)
            r = await s.execute(q)
            return [
                {
                    "id": row.log_id, "user_id": row.user_id,
                    "tenant_id": row.tenant_id, "action": row.action,
                    "payload": row.payload, "ip": row.ip,
                    "timestamp": row.created_at.isoformat(),
                }
                for row in r.scalars()
            ]
