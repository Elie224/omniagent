"""Intent Router (Rule + LLM + Fallback)."""
from omniagent.core.orchestrator.router.base import (
    Intent,
    IntentRouter,
    intent_router,
    KEYWORD_MAP,
)

__all__ = ["Intent", "IntentRouter", "intent_router", "KEYWORD_MAP"]
