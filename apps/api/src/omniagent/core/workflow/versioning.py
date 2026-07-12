"""Versioning des workflows et des schemas.

Chaque workflow est identifie par un nom et une version. Les versions sont
immutables : une fois publiee, une version ne change plus. Les clients peuvent
demander une version specifique ou la derniere stable.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class WorkflowVersion:
    name: str
    version: str  # semver : "1.0.0", "1.1.0", "2.0.0"
    deprecated: bool = False
    sunset_at: datetime | None = None

    def __str__(self) -> str:
        return f"{self.name}:{self.version}"


@dataclass
class WorkflowDefinition:
    version: WorkflowVersion
    steps: list[dict]
    input_schema: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    changelog: str = ""


class WorkflowRegistry:
    def __init__(self):
        self._definitions: dict[WorkflowVersion, WorkflowDefinition] = {}

    def register(self, definition: WorkflowDefinition) -> None:
        key = definition.version
        if key in self._definitions:
            raise ValueError(f"Workflow deja enregistre: {key}")
        self._definitions[key] = definition

    def get(self, name: str, version: str | None = None) -> WorkflowDefinition:
        if version is None:
            # Derniere version stable
            candidates = [d for d in self._definitions.values() if d.version.name == name]
            if not candidates:
                raise KeyError(f"Aucun workflow: {name}")
            return sorted(candidates, key=lambda d: d.created_at)[-1]
        key = WorkflowVersion(name, version)
        if key not in self._definitions:
            raise KeyError(f"Workflow inconnu: {key}")
        return self._definitions[key]

    def list_versions(self, name: str) -> list[str]:
        return sorted(d.version.version for d in self._definitions.values()
                       if d.version.name == name)

    def deprecate(self, name: str, version: str) -> None:
        d = self.get(name, version)
        d.version = WorkflowVersion(name, version, deprecated=True,
                                     sunset_at=d.version.sunset_at)


workflow_registry = WorkflowRegistry()