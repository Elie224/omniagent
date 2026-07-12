"""Simulation mode : dry-run et replay d un workflow sans effets de bord."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable
from uuid import uuid4


class SimulationMode(str, Enum):
    DRY_RUN = "dry_run"
    REPLAY = "replay"
    ASSERT = "assert"


@dataclass
class SimulatedStep:
    name: str
    expected_output: dict | None = None
    actual_output: dict | None = None
    passed: bool | None = None
    error: str | None = None


@dataclass
class Simulation:
    simulation_id: str = field(default_factory=lambda: str(uuid4()))
    workflow_name: str = ""
    mode: SimulationMode = SimulationMode.DRY_RUN
    steps: list[SimulatedStep] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    send_real: bool = False

    def passed(self) -> bool:
        if self.mode != SimulationMode.ASSERT:
            return True
        return all(s.passed for s in self.steps)

    def record_step(self, name: str, actual_output: dict) -> None:
        self.steps.append(SimulatedStep(name=name, actual_output=actual_output))


class SimulationRunner:
    def __init__(self, send_real: bool = False):
        self.send_real = send_real

    async def run(self, workflow: Callable, workflow_name: str,
                   inputs: dict, golden: list[dict] | None = None) -> Simulation:
        sim = Simulation(
            workflow_name=workflow_name,
            mode=SimulationMode.ASSERT if golden else SimulationMode.DRY_RUN,
            send_real=self.send_real,
        )
        try:
            await workflow(inputs, sim=sim)
            if golden:
                for i, expected in enumerate(golden):
                    if i < len(sim.steps):
                        actual = sim.steps[i].actual_output or {}
                        passed = self._deep_match(expected, actual)
                        sim.steps[i].expected_output = expected
                        sim.steps[i].passed = passed
            sim.finished_at = datetime.now(timezone.utc)
        except Exception as e:
            sim.finished_at = datetime.now(timezone.utc)
            sim.steps.append(SimulatedStep(name="workflow", error=str(e)))
        return sim

    @staticmethod
    def _deep_match(expected: dict, actual: dict) -> bool:
        for k, v in expected.items():
            if k not in actual or actual[k] != v:
                return False
        return True


def is_simulation_mode() -> bool:
    import os
    return os.environ.get("SIMULATION_MODE", "0") == "1"