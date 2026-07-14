"""Registre des connecteurs tiers (plateformes de recherche d emploi + storage)."""
from dataclasses import dataclass
from typing import Callable


@dataclass
class ConnectorSpec:
    name: str              # hunter | adzuna | france_travail | wttj | themuse | local_storage | ...
    category: str          # plateformes | storage
    factory: Callable
    requires_env: list[str]
    description: str


class ConnectorRegistry:
    def __init__(self):
        self._connectors: dict[str, ConnectorSpec] = {}

    def register(self, spec: ConnectorSpec) -> None:
        """Idempotent : un re-enregistrement avec le meme nom est ignore.

        Permet d appeler register_all() plusieurs fois (lifespan FastAPI,
        tests d integration, etc.) sans exploser.
        """
        if spec.name in self._connectors:
            return
        self._connectors[spec.name] = spec

    def get(self, name: str) -> ConnectorSpec:
        return self._connectors[name]

    def by_category(self, category: str) -> list[ConnectorSpec]:
        return [c for c in self._connectors.values() if c.category == category]


connector_registry = ConnectorRegistry()