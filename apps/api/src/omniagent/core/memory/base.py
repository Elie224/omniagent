"""Interface memoire abstraite."""
from abc import ABC, abstractmethod
from typing import Any


class MemoryBackend(ABC):
    """Toutes les memoires implementent cette interface."""

    @abstractmethod
    def get(self, key: str) -> Any | None: ...

    @abstractmethod
    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def list(self, prefix: str) -> list[tuple[str, Any]]: ...