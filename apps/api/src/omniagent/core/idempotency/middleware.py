"""Middleware FastAPI : Idempotency-Key (opt-in via header).

V2 : tenant-aware. La cle est scopee par tenant_id pour eviter les collisions
cross-tenant.
"""
from __future__ import annotations
import json
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from omniagent.auth.dependencies import get_current_user
from omniagent.core.idempotency.store import (
    IdempotencyConflictError,
    IdempotencyRecord,
    IdempotencyStore,
    hash_request,
)


log = logging.getLogger("idempotency")


_SIDE_EFFECT_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Middleware Idempotency-Key tenant-aware."""

    def __init__(self, app, store: IdempotencyStore | None = None,
                 default_ttl_s: int = 24 * 3600,
                 max_body_size: int = 1_000_000):
        super().__init__(app)
        self.store = store  # si None, fallback InMemory cree a la volee
        self._default_ttl = default_ttl_s
        self._max_body_size = max_body_size
        self._fallback_store: IdempotencyStore | None = None

    def _get_store(self) -> IdempotencyStore:
        if self.store is not None:
            return self.store
        if self._fallback_store is None:
            from omniagent.core.idempotency.store import InMemoryIdempotencyStore
            self._fallback_store = InMemoryIdempotencyStore(default_ttl_s=self._default_ttl)
        return self._fallback_store

    async def _resolve_tenant_id(self, request: Request) -> str:
        """Resout le tenant_id via auth (sans bloquer la requete)."""
        try:
            user = await get_current_user(request)
            return user.tenant_id
        except Exception:
            return "default"

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method not in _SIDE_EFFECT_METHODS:
            return await call_next(request)

        key = request.headers.get("Idempotency-Key")
        if not key:
            return await call_next(request)

        tenant_id = await self._resolve_tenant_id(request)
        store = self._get_store()

        # 1) Body
        body_bytes = await request.body()
        if len(body_bytes) > self._max_body_size:
            return JSONResponse(
                {"error": "Request body too large for idempotency"},
                status_code=413,
            )
        try:
            body = json.loads(body_bytes) if body_bytes else None
        except (ValueError, UnicodeDecodeError):
            body = body_bytes.decode("utf-8", errors="replace")
        body_hash = hash_request(request.method, request.url.path, body)

        # 2) Lookup
        existing = await self._aget(store, key, tenant_id)
        if existing is not None:
            if existing.request_hash != body_hash:
                return JSONResponse(
                    {
                        "error": "Idempotency-Key conflict",
                        "detail": "Cette cle est deja utilisee avec un body different.",
                    },
                    status_code=409,
                )
            log.info(f"Idempotency replay tenant={tenant_id} key={key[:8]}...")
            return Response(
                content=json.dumps(existing.body, default=str),
                status_code=existing.status_code,
                media_type="application/json",
                headers={"X-Idempotency-Replay": "true"},
            )

        # 3) Execute
        response = await call_next(request)

        # 4) Store si JSON
        if response.headers.get("content-type", "").startswith("application/json"):
            body_chunks = b""
            async for chunk in response.body_iterator:
                body_chunks += chunk if isinstance(chunk, bytes) else chunk.encode()
            try:
                response_body = json.loads(body_chunks) if body_chunks else None
            except (ValueError, UnicodeDecodeError):
                response_body = body_chunks.decode("utf-8", errors="replace")
            rec = IdempotencyRecord(
                key=key, request_hash=body_hash,
                status_code=response.status_code, body=response_body,
                tenant_id=tenant_id,
            )
            try:
                await self._aput(store, rec)
            except Exception as e:
                log.warning(f"Idempotency store put failed: {e}")
            return Response(
                content=body_chunks,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
        return response

    async def _aget(self, store, key, tenant_id):
        if hasattr(store, "aget"):
            return await store.aget(key, tenant_id)
        return store.get(key, tenant_id)

    async def _aput(self, store, record):
        if hasattr(store, "_aput"):
            await store._aput(record)
        elif hasattr(store, "aput"):
            await store.aput(record)
        else:
            store.put(record)
