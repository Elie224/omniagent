"""Migration entre versions de workflows."""
from __future__ import annotations
from typing import Callable


MigrationFn = Callable[[dict], dict]


class MigrationRegistry:
    def __init__(self):
        self._migrations: dict[tuple[str, str, str], MigrationFn] = {}
        # cle = (workflow_name, from_version, to_version)

    def register(self, workflow_name: str, from_version: str, to_version: str,
                 fn: MigrationFn) -> None:
        self._migrations[(workflow_name, from_version, to_version)] = fn

    def migrate(self, workflow_name: str, from_version: str,
                to_version: str, payload: dict) -> dict:
        if from_version == to_version:
            return payload
        fn = self._migrations.get((workflow_name, from_version, to_version))
        if fn is None:
            raise KeyError(
                f"Pas de migration pour {workflow_name}: {from_version} -> {to_version}"
            )
        return fn(payload)


migration_registry = MigrationRegistry()