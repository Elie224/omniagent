"""Idempotency-Key : evite les doubles-executions cote API.

Conventions :
- Header HTTP `Idempotency-Key: <uuid>` (optionnel, opt-in par client)
- Le store conserve la reponse de la 1re requete pour la meme cle
- Une 2e requete avec la meme cle + meme hash de body -> renvoie la reponse stockee
- Une 2e requete avec la meme cle + hash different -> 409 Conflict
- Sans header -> comportement normal (pas d idempotence)
- TTL configurable (defaut 24h)
"""
from omniagent.core.idempotency.store import (
    IdempotencyStore,
    InMemoryIdempotencyStore,
    IdempotencyRecord,
    IdempotencyConflictError,
)
from omniagent.core.idempotency.middleware import IdempotencyMiddleware

__all__ = [
    "IdempotencyStore", "InMemoryIdempotencyStore", "IdempotencyRecord",
    "IdempotencyConflictError", "IdempotencyMiddleware",
]
