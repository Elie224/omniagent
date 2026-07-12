"""Monitoring Agent : detecte les erreurs et relance les taches via Celery."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any


class MonitoringAgent:
    """Surveille les executions d''agents et declenche des reprises.

    - suit les taux d''erreur par agent
    - detecte les agents silencieusement bloques
    - declenche un retry (via l''AgentManager) si retryable
    - alerte via notification_agent si le seuil est depasse
    """

    def __init__(self, error_threshold: float = 0.5, window_minutes: int = 15):
        self._lock = RLock()
        self._runs: dict[str, list[dict]] = defaultdict(list)  # agent_name -> [events]
        self._threshold = error_threshold
        self._window = timedelta(minutes=window_minutes)

    def record(self, agent_name: str, status: str, run_id: str,
               error: str | None = None, retry_count: int = 0) -> None:
        with self._lock:
            self._runs[agent_name].append({
                "run_id": run_id, "status": status, "error": error,
                "retry_count": retry_count, "ts": datetime.now(timezone.utc),
            })
            # Nettoyage hors fenetre
            cutoff = datetime.now(timezone.utc) - self._window
            self._runs[agent_name] = [r for r in self._runs[agent_name] if r["ts"] > cutoff]

    def get_error_rate(self, agent_name: str) -> dict:
        with self._lock:
            runs = self._runs.get(agent_name, [])
            if not runs:
                return {"agent": agent_name, "total": 0, "errors": 0, "rate": 0.0,
                        "alert": False}
            errors = sum(1 for r in runs if r["status"] == "failed")
            rate = errors / len(runs)
            return {
                "agent": agent_name, "total": len(runs), "errors": errors,
                "rate": round(rate, 3), "alert": rate >= self._threshold,
            }

    def detect_zombies(self) -> list[str]:
        """Liste les agents qui tournent depuis trop longtemps sans succes."""
        with self._lock:
            cutoff = datetime.now(timezone.utc) - self._window
            zombies = []
            for agent_name, runs in self._runs.items():
                recent = [r for r in runs if r["ts"] > cutoff]
                if not recent:
                    continue
                running = [r for r in recent if r["status"] == "running"]
                if len(running) > 3:  # plus de 3 runs en cours dans la fenetre
                    zombies.append(agent_name)
            return zombies

    def should_retry(self, agent_name: str) -> bool:
        s = self.get_error_rate(agent_name)
        return s["alert"] and s["total"] >= 3

    async def trigger_retry(self, agent_name: str, user_id: str, payload: dict) -> str:
        """Relance une tache en arriere-plan via Celery."""
        from omniagent.core.celery_app import celery_app
        job = celery_app.send_task(
            f"agent.{agent_name}.run",
            kwargs={"user_id": user_id, "input_data": payload},
        )
        return job.id

    def snapshot(self) -> dict:
        with self._lock:
            return {a: self.get_error_rate(a) for a in self._runs.keys()}


_monitoring_agent: MonitoringAgent | None = None


def get_monitoring_agent() -> MonitoringAgent:
    global _monitoring_agent
    if _monitoring_agent is None:
        _monitoring_agent = MonitoringAgent()
    return _monitoring_agent


async def run(input_data: dict, user_id: str) -> dict:
    action = input_data.get("action", "snapshot")
    agent = get_monitoring_agent()
    if action == "record":
        agent.record(input_data["agent_name"], input_data["status"],
                     input_data["run_id"], input_data.get("error"),
                     input_data.get("retry_count", 0))
        return {"recorded": True}
    if action == "error_rate":
        return agent.get_error_rate(input_data["agent_name"])
    if action == "zombies":
        return {"zombies": agent.detect_zombies()}
    if action == "retry":
        return {"job_id": await agent.trigger_retry(
            input_data["agent_name"], user_id, input_data.get("payload", {})
        )}
    return {"snapshot": agent.snapshot()}
