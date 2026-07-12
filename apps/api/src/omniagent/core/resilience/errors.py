"""Classification des erreurs agent.

Chaque erreur est categorisee en :
- TRANSIENT  : retryable, on reessaie plus tard
- RATE_LIMIT : retryable, on attend avant de reessayer
- FATAL      : non-retryable, on remonte immediatement
- PARTIAL    : l agent a partiellement reussi, on tente une compensation
- USER_ERROR : input utilisateur invalide, ne pas retry
"""
from __future__ import annotations
from enum import Enum


class ErrorCategory(str, Enum):
    TRANSIENT = "transient"
    RATE_LIMIT = "rate_limit"
    FATAL = "fatal"
    PARTIAL = "partial"
    USER_ERROR = "user_error"


class AgentError(Exception):
    """Exception enrichie portant la categorie d erreur."""

    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.TRANSIENT,
                 original: Exception | None = None, retry_after_s: float = 0):
        super().__init__(message)
        self.message = message
        self.category = category
        self.original = original
        self.retry_after_s = retry_after_s

    @property
    def is_retryable(self) -> bool:
        return self.category in {ErrorCategory.TRANSIENT, ErrorCategory.RATE_LIMIT}


# Patterns reconnus automatiquement
RATE_LIMIT_PATTERNS = ("rate limit", "too many requests", "429", "quota exceeded")
TRANSIENT_PATTERNS = ("timeout", "connection", "503", "502", "504", "temporarily unavailable")
FATAL_PATTERNS = ("401", "403", "unauthorized", "forbidden", "not found", "404")
USER_ERROR_PATTERNS = ("invalid", "validation", "missing required", "bad request", "400")


def classify_error(error: Exception | str) -> ErrorCategory:
    """Classe une exception ou un message en categorie d erreur."""
    msg = str(error).lower() if isinstance(error, Exception) else str(error).lower()
    if any(p in msg for p in RATE_LIMIT_PATTERNS):
        return ErrorCategory.RATE_LIMIT
    if any(p in msg for p in FATAL_PATTERNS):
        return ErrorCategory.FATAL
    if any(p in msg for p in USER_ERROR_PATTERNS):
        return ErrorCategory.USER_ERROR
    if any(p in msg for p in TRANSIENT_PATTERNS):
        return ErrorCategory.TRANSIENT
    return ErrorCategory.TRANSIENT  # par defaut, on suppose retryable


def wrap_exception(error: Exception) -> AgentError:
    """Enveloppe une exception standard en AgentError categorisee."""
    category = classify_error(error)
    retry_after = 60.0 if category == ErrorCategory.RATE_LIMIT else 0.0
    return AgentError(str(error), category=category, original=error, retry_after_s=retry_after)