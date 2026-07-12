"""Registry de workflows declaratifs.

Un workflow est un DAG de steps. Chaque step reference un `agent_name`
connu du registre global (JOB_AGENTS, transverse.subagents, etc.).

API :
- register(workflow)
- get(name)
- list() -> dict[name, summary]
- names() -> list[str]
- exists(name) -> bool
"""
from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Any


@dataclass
class WorkflowStep:
    """Une etape dans un workflow declaratif."""
    name: str                       # cle interne (snake_case)
    agent_name: str                 # nom d agent a appeler
    depends_on: list[str] = field(default_factory=list)
    input_template: dict = field(default_factory=dict)
    description: str = ""
    timeout_s: int = 300
    optional: bool = False          # si True, l echec ne fait pas tomber le DAG


@dataclass
class WorkflowDefinition:
    """Definition complete d un workflow executable."""
    name: str                       # cle publique (ex: "job_search_dag")
    version: str
    description: str
    intent: str                     # intent declencheur (router side)
    steps: list[WorkflowStep]
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "intent": self.intent,
            "tags": self.tags,
            "steps": [
                {
                    "name": s.name,
                    "agent_name": s.agent_name,
                    "depends_on": s.depends_on,
                    "description": s.description,
                    "optional": s.optional,
                    "timeout_s": s.timeout_s,
                }
                for s in self.steps
            ],
            "graph": {
                "nodes": [s.name for s in self.steps],
                "edges": [
                    {"from": d, "to": s.name}
                    for s in self.steps for d in s.depends_on
                ],
            },
        }


class WorkflowRegistry:
    """Registre thread-safe des workflows."""

    def __init__(self):
        self._lock = RLock()
        self._workflows: dict[str, WorkflowDefinition] = {}

    def register(self, workflow: WorkflowDefinition) -> None:
        with self._lock:
            if workflow.name in self._workflows:
                raise ValueError(f"workflow deja enregistre: {workflow.name}")
            self._validate(workflow)
            self._workflows[workflow.name] = workflow

    def get(self, name: str) -> WorkflowDefinition | None:
        with self._lock:
            return self._workflows.get(name)

    def exists(self, name: str) -> bool:
        with self._lock:
            return name in self._workflows

    def names(self) -> list[str]:
        with self._lock:
            return sorted(self._workflows.keys())

    def list(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "name": w.name,
                    "version": w.version,
                    "intent": w.intent,
                    "description": w.description,
                    "tags": w.tags,
                    "step_count": len(w.steps),
                    "agents": sorted({s.agent_name for s in w.steps}),
                }
                for w in self._workflows.values()
            ]

    def _validate(self, w: WorkflowDefinition) -> None:
        names = {s.name for s in w.steps}
        if len(names) != len(w.steps):
            raise ValueError(f"workflow {w.name}: step names dupliques")
        for s in w.steps:
            unknown = set(s.depends_on) - names
            if unknown:
                raise ValueError(
                    f"workflow {w.name}: step {s.name} reference unknown depends_on {unknown}"
                )
        # detection cycle trivial
        done: set[str] = set()
        remaining = {s.name: s.depends_on for s in w.steps}
        for _ in range(len(w.steps) + 1):
            progressed = False
            for n, deps in list(remaining.items()):
                if all(d in done for d in deps):
                    done.add(n)
                    del remaining[n]
                    progressed = True
            if not progressed:
                if remaining:
                    raise ValueError(f"workflow {w.name}: cycle detecte {remaining}")
                return
        return


workflow_registry = WorkflowRegistry()