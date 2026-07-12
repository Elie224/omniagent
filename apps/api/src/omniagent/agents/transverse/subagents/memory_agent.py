"""Memory Agent : pilote les 4 niveaux de memoire (session, user, vector, domain)."""
from __future__ import annotations
from typing import Any


class MemoryAgent:
    def __init__(self, memory_stack):
        self._memory = memory_stack

    def remember(self, scope: str, key: str, value: Any, ttl_seconds: int | None = None) -> dict:
        backend = self._get_backend(scope)
        backend.set(key, value, ttl_seconds=ttl_seconds)
        return {"scope": scope, "key": key, "stored": True}

    def recall(self, scope: str, key: str) -> Any | None:
        return self._get_backend(scope).get(key)

    def search_similar(self, query: str, top_k: int = 5) -> list[dict]:
        return self._memory.vector.search(query, top_k=top_k)

    def add_exclusion(self, contact_id: str, reason: str, ttl_days: int = 90) -> None:
        self._memory.domain.add_exclusion(contact_id, reason, ttl_days)

    def is_excluded(self, contact_id: str, reason: str | None = None) -> bool:
        return self._memory.domain.is_excluded(contact_id, reason)

    def _get_backend(self, scope: str):
        if scope == "session": return self._memory.session
        if scope == "user":   return self._memory.user
        if scope == "vector": return self._memory.vector
        if scope == "domain": return self._memory.domain
        raise ValueError(f"Scope memoire inconnu: {scope}")


_memory_agent: MemoryAgent | None = None


def get_memory_agent() -> MemoryAgent:
    global _memory_agent
    if _memory_agent is None:
        from omniagent.core.memory.factory import build_memory_stack
        _memory_agent = MemoryAgent(build_memory_stack(db_session=None, pgvector_conn=None))
    return _memory_agent


async def run(input_data: dict, user_id: str) -> dict:
    action = input_data.get("action", "recall")
    scope = input_data.get("scope", "session")
    key = input_data.get("key", "")
    value = input_data.get("value")
    agent = get_memory_agent()
    try:
        if action == "remember":
            return agent.remember(scope, key, value, input_data.get("ttl_seconds"))
        if action == "search":
            return {"results": agent.search_similar(input_data.get("query", ""),
                                                     input_data.get("top_k", 5))}
        if action == "add_exclusion":
            agent.add_exclusion(input_data["contact_id"], input_data["reason"],
                                input_data.get("ttl_days", 90))
            return {"exclusion_added": True}
        return {"value": agent.recall(scope, key)}
    except ValueError as e:
        return {"error": str(e), "stored": False, "value": None}