"""Registre des capabilities : permet a n importe quel composant de decouvrir
qui sait faire quoi (agent x tool x connector x module)."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CapabilityKind(str, Enum):
    SEARCH = "search"
    SEND = "send"
    ANALYZE = "analyze"
    GENERATE = "generate"
    SYNC = "sync"
    NOTIFY = "notify"
    INDEX = "index"
    REMEMBER = "remember"


@dataclass
class Capability:
    name: str
    kind: CapabilityKind
    owner: str  # nom de l agent qui expose la capability
    owner_kind: str  # "agent" | "tool" | "connector"
    description: str
    inputs: dict = field(default_factory=dict)
    outputs: dict = field(default_factory=dict)
    requires: list[str] = field(default_factory=list)  # autres capabilities requises


class CapabilityRegistry:
    def __init__(self):
        self._capabilities: dict[str, Capability] = {}

    def register(self, cap: Capability) -> None:
        if cap.name in self._capabilities:
            raise ValueError(f"Capability deja enregistree: {cap.name}")
        self._capabilities[cap.name] = cap

    def get(self, name: str) -> Capability:
        if name not in self._capabilities:
            raise KeyError(f"Capability inconnue: {name}")
        return self._capabilities[name]

    def find_by_kind(self, kind: CapabilityKind) -> list[Capability]:
        return [c for c in self._capabilities.values() if c.kind == kind]

    def find_by_owner(self, owner: str) -> list[Capability]:
        return [c for c in self._capabilities.values() if c.owner == owner]

    def list_all(self) -> list[Capability]:
        return list(self._capabilities.values())

    def can_serve(self, owner: str, cap_name: str) -> bool:
        """Verifie qu un owner peut repondre a une capability (avec ses deps)."""
        cap = self.get(cap_name)
        if cap.owner != owner:
            return False
        return all(self.can_serve(owner, req) for req in cap.requires)


capability_registry = CapabilityRegistry()


def register_default_capabilities() -> None:
    """Enregistre les capabilities par defaut au demarrage."""
    from omniagent.core.registry.agent_registry import registry as agent_reg

    for spec in agent_reg.all():
        kind = CapabilityKind.GENERATE
        if "search" in spec.name or "_job" in spec.name or "scraping" in spec.description.lower():
            kind = CapabilityKind.SEARCH
        elif "notification" in spec.name:
            kind = CapabilityKind.NOTIFY
        elif "analyse" in spec.name or "scoring" in spec.description.lower():
            kind = CapabilityKind.ANALYZE
        elif "sync" in spec.description.lower():
            kind = CapabilityKind.SYNC
        elif "memory" in spec.name or "knowledge" in spec.name:
            kind = CapabilityKind.REMEMBER if "memory" in spec.name else CapabilityKind.INDEX
        elif "communication" in spec.name or "vocal" in spec.name or "relanc" in spec.description.lower():
            kind = CapabilityKind.SEND
        capability_registry.register(Capability(
            name=f"{spec.name}.run",
            kind=kind,
            owner=spec.name,
            owner_kind="agent",
            description=spec.description,
            requires=spec.dependencies,
        ))