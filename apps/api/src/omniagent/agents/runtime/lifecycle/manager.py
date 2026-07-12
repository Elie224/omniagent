"""Lifecycle des agents : start, monitor, stop, restart.

Suit le pattern des services long-running avec hooks d arret propre.
"""
from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import Lock
from typing import Any, Awaitable, Callable
from uuid import uuid4


class AgentLifecycleState(str, Enum):
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class LifecycleHooks:
    on_start: Callable[[], Awaitable[None]] | None = None
    on_stop: Callable[[], Awaitable[None]] | None = None
    on_pause: Callable[[], Awaitable[None]] | None = None
    on_resume: Callable[[], Awaitable[None]] | None = None
    on_failure: Callable[[Exception], Awaitable[None]] | None = None


@dataclass
class AgentInstance:
    instance_id: str
    agent_name: str
    state: AgentLifecycleState = AgentLifecycleState.CREATED
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    restart_count: int = 0
    last_error: str | None = None
    hooks: LifecycleHooks = field(default_factory=LifecycleHooks)
    context: Any = None  # IsolatedContext

    def uptime_s(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.stopped_at or datetime.now(timezone.utc)
        return (end - self.started_at).total_seconds()


class AgentLifecycleManager:
    """Gere le cycle de vie complet d une instance d agent."""

    def __init__(self):
        self._instances: dict[str, AgentInstance] = {}
        self._lock: asyncio.Lock | None = None

    async def create(self, agent_name: str, context=None,
                     hooks: LifecycleHooks | None = None) -> AgentInstance:
        inst = AgentInstance(
            instance_id=str(uuid4()),
            agent_name=agent_name,
            hooks=hooks or LifecycleHooks(),
            context=context,
        )
        async with self._get_lock():
            self._instances[inst.instance_id] = inst
        return inst

    async def start(self, instance_id: str) -> None:
        async with self._get_lock():
            inst = self._instances[instance_id]
            inst.state = AgentLifecycleState.STARTING
        if inst.hooks.on_start:
            await inst.hooks.on_start()
        async with self._get_lock():
            inst.state = AgentLifecycleState.RUNNING
            inst.started_at = datetime.now(timezone.utc)

    async def stop(self, instance_id: str) -> None:
        async with self._get_lock():
            inst = self._instances[instance_id]
            inst.state = AgentLifecycleState.STOPPING
        if inst.hooks.on_stop:
            try:
                await inst.hooks.on_stop()
            except Exception as e:
                inst.last_error = str(e)
        async with self._get_lock():
            inst.state = AgentLifecycleState.STOPPED
            inst.stopped_at = datetime.now(timezone.utc)

    async def pause(self, instance_id: str) -> None:
        async with self._get_lock():
            inst = self._instances[instance_id]
            inst.state = AgentLifecycleState.PAUSED
        if inst.hooks.on_pause:
            await inst.hooks.on_pause()

    async def resume(self, instance_id: str) -> None:
        async with self._get_lock():
            inst = self._instances[instance_id]
            inst.state = AgentLifecycleState.RUNNING
        if inst.hooks.on_resume:
            await inst.hooks.on_resume()

    async def fail(self, instance_id: str, error: Exception) -> None:
        async with self._get_lock():
            inst = self._instances[instance_id]
            inst.state = AgentLifecycleState.FAILED
            inst.last_error = str(error)
            inst.stopped_at = datetime.now(timezone.utc)
        if inst.hooks.on_failure:
            try:
                await inst.hooks.on_failure(error)
            except Exception:
                pass

    async def restart(self, instance_id: str) -> None:
        await self.stop(instance_id)
        async with self._get_lock():
            inst = self._instances[instance_id]
            inst.restart_count += 1
        await self.start(instance_id)

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def get(self, instance_id: str) -> AgentInstance | None:
        return self._instances.get(instance_id)

    def list_active(self) -> list[dict]:
        return [{"id": i.instance_id, "agent": i.agent_name, "state": i.state.value,
                 "uptime_s": round(i.uptime_s(), 1), "restarts": i.restart_count}
                for i in self._instances.values()
                if i.state in {AgentLifecycleState.RUNNING, AgentLifecycleState.PAUSED}]


lifecycle_manager = AgentLifecycleManager()
