"""Saga pattern : orchestration des compensations en cas d echec partiel."""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from uuid import uuid4

from omniagent.core.events import emit_workflow_rolled_back


log = logging.getLogger("saga")


@dataclass
class SagaStep:
    name: str
    action: Callable[[dict], Awaitable[dict]]
    compensation: Callable[[dict], Awaitable[None]] | None = None
    result: dict | None = None
    executed: bool = False
    compensated: bool = False
    error: str | None = None


@dataclass
class Saga:
    workflow_id: str = field(default_factory=lambda: str(uuid4()))
    steps: list[SagaStep] = field(default_factory=list)
    state: dict = field(default_factory=dict)
    status: str = "pending"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    user_id: str = "system"

    def add_step(self, name: str, action: Callable, compensation: Callable | None = None) -> "Saga":
        self.steps.append(SagaStep(name=name, action=action, compensation=compensation))
        return self

    async def execute(self) -> dict:
        self.status = "running"
        self.started_at = datetime.now(timezone.utc)
        executed: list[SagaStep] = []
        try:
            for step in self.steps:
                log.info(f"[Saga {self.workflow_id}] running step {step.name}")
                step.result = await step.action(self.state)
                step.executed = True
                self.state[step.name] = step.result
                executed.append(step)
            self.status = "completed"
            self.finished_at = datetime.now(timezone.utc)
            return {"status": "completed", "results": {s.name: s.result for s in self.steps}}
        except Exception as e:
            self.status = "failed"
            self.error = str(e)
            self.finished_at = datetime.now(timezone.utc)
            log.error(f"[Saga {self.workflow_id}] failed: {e}")
            compensations = await self._compensate(executed)
            return {"status": "rolled_back", "error": str(e),
                    "compensations": compensations,
                    "results": {s.name: s.result for s in executed}}

    async def _compensate(self, executed: list[SagaStep]) -> list[str]:
        compensations: list[str] = []
        for step in reversed(executed):
            if step.compensation is None:
                continue
            try:
                log.info(f"[Saga {self.workflow_id}] compensating {step.name}")
                await step.compensation(self.state)
                step.compensated = True
                compensations.append(step.name)
            except Exception as e:
                log.error(f"[Saga {self.workflow_id}] compensation of {step.name} failed: {e}")
        self.status = "rolled_back"
        await emit_workflow_rolled_back(self.workflow_id, self.user_id, compensations)
        return compensations


class SagaBuilder:
    def __init__(self, user_id: str = "system"):
        self._saga = Saga(user_id=user_id)

    def step(self, name: str, action: Callable, compensation: Callable | None = None) -> "SagaBuilder":
        self._saga.add_step(name, action, compensation)
        return self

    def build(self) -> Saga:
        return self._saga

    async def execute(self) -> dict:
        return await self._saga.execute()

    @property
    def status(self) -> str:
        return self._saga.status

    @property
    def state(self) -> dict:
        return self._saga.state