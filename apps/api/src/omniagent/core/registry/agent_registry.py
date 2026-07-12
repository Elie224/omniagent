"""Registre centralise des agents disponibles (pour l''orchestrateur et le manager)."""
from dataclasses import dataclass
from enum import Enum
from typing import Callable


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class AgentSpec:
    name: str
    module: str           # emploi | marketing | recouvrement | meta
    role: str             # coordinateur | specialiste
    description: str
    run_fn: Callable
    dependencies: list[str]
    max_concurrency: int = 5
    timeout_seconds: int = 300


class AgentRegistry:
    def __init__(self):
        self._agents: dict[str, AgentSpec] = {}

    def register(self, spec: AgentSpec) -> None:
        """Idempotent : un re-enregistrement avec le meme nom est ignore.

        Permet d appeler register_all() plusieurs fois (lifespan FastAPI,
        tests, multi-worker au reload) sans exploser. On n ecraserait
        pas une spec existante par precaution : si une autre definition
        a ete enregistree entre-temps, c est probablement intentionnel.
        """
        if spec.name in self._agents:
            return
        self._agents[spec.name] = spec

    def get(self, name: str) -> AgentSpec:
        if name not in self._agents:
            raise KeyError(f"Agent inconnu: {name}")
        return self._agents[name]

    def list_by_module(self, module: str) -> list[AgentSpec]:
        return [a for a in self._agents.values() if a.module == module]

    def all(self) -> list[AgentSpec]:
        return list(self._agents.values())


registry = AgentRegistry()