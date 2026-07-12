"""Planning Agent : planifie des taches futures (cron-like, declenche via Celery beat)."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from threading import RLock


class Frequency(str, Enum):
    ONCE = "once"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class ScheduledTask:
    task_id: str
    user_id: str
    agent_name: str
    payload: dict
    frequency: Frequency
    next_run: datetime
    last_run: datetime | None = None
    enabled: bool = True
    run_count: int = 0


class PlanningAgent:
    """Stocke et calcule le prochain run des taches planifiees."""

    def __init__(self):
        self._lock = RLock()
        self._tasks: dict[str, ScheduledTask] = {}

    def schedule(self, user_id: str, agent_name: str, payload: dict,
                 frequency: Frequency, start_at: datetime | None = None) -> str:
        task_id = f"{user_id}_{agent_name}_{int(datetime.now(timezone.utc).timestamp())}"
        next_run = start_at or datetime.now(timezone.utc) + timedelta(minutes=1)
        with self._lock:
            self._tasks[task_id] = ScheduledTask(
                task_id=task_id, user_id=user_id, agent_name=agent_name,
                payload=payload, frequency=frequency, next_run=next_run,
            )
        return task_id

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            return self._tasks.pop(task_id, None) is not None

    def due_tasks(self, now: datetime | None = None) -> list[ScheduledTask]:
        now = now or datetime.now(timezone.utc)
        with self._lock:
            return [t for t in self._tasks.values() if t.enabled and t.next_run <= now]

    def mark_run(self, task_id: str) -> None:
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                return
            t.last_run = datetime.now(timezone.utc)
            t.run_count += 1
            t.next_run = self._next(t.frequency, t.last_run)

    @staticmethod
    def _next(freq: Frequency, last: datetime) -> datetime:
        if freq == Frequency.ONCE:    return last + timedelta(days=365 * 100)
        if freq == Frequency.HOURLY:  return last + timedelta(hours=1)
        if freq == Frequency.DAILY:   return last + timedelta(days=1)
        if freq == Frequency.WEEKLY:  return last + timedelta(weeks=1)
        if freq == Frequency.MONTHLY: return last + timedelta(days=30)
        return last

    def list_for_user(self, user_id: str) -> list[ScheduledTask]:
        with self._lock:
            return [t for t in self._tasks.values() if t.user_id == user_id]

    def tick(self) -> list[dict]:
        """A executer periodiquement (par un cron externe ou un endpoint)."""
        ready = self.due_tasks()
        for t in ready:
            t.last_run = datetime.now(timezone.utc)
            t.run_count += 1
            t.next_run = self._next(t.frequency, t.last_run)
        return [{"task_id": t.task_id, "agent_name": t.agent_name,
                 "user_id": t.user_id, "payload": t.payload} for t in ready]


_planning_agent: PlanningAgent | None = None


def get_planning_agent() -> PlanningAgent:
    global _planning_agent
    if _planning_agent is None:
        _planning_agent = PlanningAgent()
    return _planning_agent


async def run(input_data: dict, user_id: str) -> dict:
    action = input_data.get("action", "list")
    agent = get_planning_agent()
    if action == "schedule":
        from datetime import datetime
        start = input_data.get("start_at")
        task_id = agent.schedule(
            user_id=user_id,
            agent_name=input_data["agent_name"],
            payload=input_data.get("payload", {}),
            frequency=Frequency(input_data.get("frequency", "daily")),
            start_at=datetime.fromisoformat(start) if start else None,
        )
        return {"task_id": task_id, "scheduled": True}
    if action == "cancel":
        return {"cancelled": agent.cancel(input_data["task_id"])}
    if action == "tick":
        return {"due": agent.tick()}
    return {"tasks": [
        {"id": t.task_id, "agent": t.agent_name, "freq": t.frequency.value,
         "next_run": t.next_run.isoformat(), "enabled": t.enabled}
        for t in agent.list_for_user(user_id)
    ]}
