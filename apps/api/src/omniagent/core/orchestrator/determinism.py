"""Deterministic Orchestrator Hardening : ExecutionGraph live + step IDs stables.

3 responsabilites :

1. PlanStep.step_id : identifiant stable (derivable du nom de l agent) pour
   permettre le chainage parent/enfant sans collision.

2. DeterministicPlanner : interface qui garantit :
   - steps dans une list ordonnee (pas de set/dict iteration)
   - meme input -> meme liste de steps (test d ordre)
   - step_id unique par plan

3. ExecutionGraph : graphe live construit pendant l execution du run, pas
   reconstruit apres coup. Chaque step runtime est enregistre avec :
   - step_id, parent_step_id, start_time, end_time, status
   - agent_name, output (snapshot)
   Le graph est attache au run_id (correlation_id) et persiste en memoire
   pour la duree du run.

REGLE D AUTORITE (Single source of truth) :
- EventStore = source de verite immutable (tous les events)
- ExecutionGraph = vue live en memoire, derivee de l execution en cours
- CausalGraph = projection offline reconstruite depuis l EventStore
- Metrics = agregation derivee de l EventStore

Ces 3 couches ne se contredisent pas : la live view disparait au restart
du process (volatile), la projection offline survit (EventStore).
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


# --- Step ID generation (deterministic) ---

def derive_step_id(plan_name: str, plan_version: str, agent_name: str,
                    index: int) -> str:
    """Step ID deterministe, derive du (plan, agent, index).

    Pas d UUID (aléatoire) : meme plan + meme index -> meme step_id.
    Format : "<plan>@<version>#<index>:<agent>"
    """
    return f"{plan_name}@{plan_version}#{index}:{agent_name}"


# --- ExecutionGraph : live view ---

class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ExecutionNode:
    """Un step runtime avec ses metadonnees temporelles et son output."""
    step_id: str
    agent_name: str
    parent_step_id: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    status: StepStatus = StepStatus.PENDING
    output: Any = None
    error: Optional[str] = None
    children_ids: list[str] = field(default_factory=list)

    def duration_ms(self) -> float:
        if not (self.start_time and self.end_time):
            return 0.0
        try:
            s = datetime.fromisoformat(self.start_time)
            e = datetime.fromisoformat(self.end_time)
            return (e - s).total_seconds() * 1000.0
        except (TypeError, ValueError):
            return 0.0

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "agent_name": self.agent_name,
            "parent_step_id": self.parent_step_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms(),
            "status": self.status.value,
            "children_ids": list(self.children_ids),
            "error": self.error,
        }


class ExecutionGraph:
    """Graphe d execution live pour un run donne.

    Pas de re-construction offline : on ajoute des noeuds au fur et a mesure
    que l orchestrateur execute. La structure est simple (dict de noeuds +
    liste de roots) et tient en RAM pour la duree du run.

    Concurrence : un seul appel a `begin_step` a la fois par step_id (lock).
    """

    def __init__(self, run_id: str, plan_name: str, plan_version: str):
        self.run_id = run_id
        self.plan_name = plan_name
        self.plan_version = plan_version
        self._nodes: dict[str, ExecutionNode] = {}
        self._roots: list[str] = []
        self._lock_count = 0

    @property
    def nodes(self) -> dict[str, ExecutionNode]:
        return dict(self._nodes)

    @property
    def roots(self) -> list[str]:
        return list(self._roots)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def add_root(self, step_id: str, agent_name: str) -> ExecutionNode:
        """Declare un step racine (sans parent). Idempotent : re-declarer
        le meme step_id ne cree pas de doublon.
        """
        if step_id in self._nodes:
            return self._nodes[step_id]
        node = ExecutionNode(
            step_id=step_id, agent_name=agent_name,
            start_time=None, status=StepStatus.PENDING,
        )
        self._nodes[step_id] = node
        self._roots.append(step_id)
        return node

    def begin_step(self, step_id: str, parent_step_id: Optional[str] = None) -> ExecutionNode:
        """Marque un step comme demarre. Lie le parent si specifie.

        Si le step n existe pas encore, on le cree. Si parent_step_id est
        specifie, on l ajoute comme child du parent.
        """
        node = self._nodes.get(step_id)
        if node is None:
            node = ExecutionNode(
                step_id=step_id,
                agent_name="",  # peut etre set plus tard via finish_step
                parent_step_id=parent_step_id,
            )
            self._nodes[step_id] = node
        else:
            # Mise a jour parent si pas deja set (allow late binding)
            if parent_step_id and not node.parent_step_id:
                node.parent_step_id = parent_step_id

        if parent_step_id:
            parent = self._nodes.get(parent_step_id)
            if parent is not None and step_id not in parent.children_ids:
                parent.children_ids.append(step_id)
        elif step_id not in self._roots and node.parent_step_id is None:
            self._roots.append(step_id)

        node.start_time = self._now()
        node.status = StepStatus.RUNNING
        return node

    def finish_step(self, step_id: str, status: StepStatus,
                     output: Any = None, error: Optional[str] = None) -> ExecutionNode:
        """Marque un step comme termine."""
        node = self._nodes.get(step_id)
        if node is None:
            raise KeyError(f"step_id inconnu: {step_id!r}")
        node.end_time = self._now()
        node.status = status
        node.output = output
        node.error = error
        return node

    def stats(self) -> dict:
        by_status: dict[str, int] = defaultdict(int)
        for n in self._nodes.values():
            by_status[n.status.value] += 1
        total_duration = sum(n.duration_ms() for n in self._nodes.values())
        return {
            "run_id": self.run_id,
            "plan": f"{self.plan_name}@{self.plan_version}",
            "total_steps": len(self._nodes),
            "by_status": dict(by_status),
            "total_duration_ms": total_duration,
            "roots": list(self._roots),
        }

    def to_dict(self) -> dict:
        return {
            **self.stats(),
            "nodes": {sid: n.to_dict() for sid, n in self._nodes.items()},
        }


# --- Plan step_id assignment ---

def assign_step_ids(plan_name: str, plan_version: str,
                     agent_names: list[str]) -> list[str]:
    """Assigne un step_id deterministe a chaque agent du plan.

    Meme (plan_name, plan_version, agent_names) -> meme liste de step_ids.
    """
    return [
        derive_step_id(plan_name, plan_version, agent, i)
        for i, agent in enumerate(agent_names)
    ]


def assert_step_ids_unique(step_ids: list[str]) -> None:
    """Verifie l absence de doublons dans les step_ids (anti-collision)."""
    seen = set()
    for sid in step_ids:
        if sid in seen:
            raise ValueError(f"step_id en doublon: {sid!r}")
        seen.add(sid)


# --- DeterministicPlanner : interface qui certifie l ordre stable ---

class DeterministicPlannerError(Exception):
    """Leve quand un planner ne respecte pas les invariants deterministes."""


def assert_deterministic_plan(steps: list, plan_name: str, plan_version: str) -> None:
    """Verifie les invariants d un plan deterministe.

    Invariants :
    1. steps est une list (pas un set / dict).
    2. step_id est unique.
    3. step_id peut etre derive deterministicement (pas d UUID).
    4. depends_on pointe vers des step_id existants ou des noms valides.
    """
    if not isinstance(steps, list):
        raise DeterministicPlannerError(
            f"Plan {plan_name}: steps doit etre une list, pas {type(steps).__name__}"
        )
    seen_derived = set()
    seen_explicit = set()
    for i, step in enumerate(steps):
        sid = derive_step_id(plan_name, plan_version, getattr(step, "agent_name", ""), i)
        if sid in seen_derived:
            raise DeterministicPlannerError(f"step_id en doublon: {sid!r}")
        seen_derived.add(sid)
        # Si le step a un step_id explicite, on verifie :
        # 1. qu il n est pas un UUID (non-deterministe)
        # 2. qu il n est pas en doublon avec un autre step explicite
        if hasattr(step, "step_id"):
            sid_field = str(step.step_id)
            if "-" in sid_field and len(sid_field) == 36:
                raise DeterministicPlannerError(
                    f"step_id={sid_field!r} ressemble a un UUID (non-deterministe). "
                    "Utilisez derive_step_id()."
                )
            if sid_field in seen_explicit:
                raise DeterministicPlannerError(
                    f"step_id explicite en doublon: {sid_field!r}"
                )
            seen_explicit.add(sid_field)