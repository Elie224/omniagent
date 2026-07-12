"""Contrat de plugin : interface pour tout connecteur hot-pluggable."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PluginMetadata:
    name: str
    version: str
    category: str
    author: str = "unknown"
    description: str = ""
    requires_env: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


class Plugin(ABC):
    """Contrat de base pour tout plugin (connecteur)."""

    metadata: PluginMetadata

    @abstractmethod
    def instantiate(self, config: dict) -> Any:
        """Cree une instance du plugin avec la config donnee."""

    @abstractmethod
    async def health_check(self, instance: Any) -> bool:
        """Verifie que l instance fonctionne."""

    @abstractmethod
    def shutdown(self, instance: Any) -> None:
        """Libere proprement les ressources."""


class PluginError(Exception):
    pass