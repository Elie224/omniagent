"""Suivi des KPIs metier (vs technique) : taux de conversion, fiabilite, cout."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any


@dataclass
class AgentBusinessScore:
    agent_name: str
    runs: int = 0
    successes: int = 0
    failures: int = 0
    total_cost_usd: float = 0.0
    total_duration_ms: float = 0.0
    business_value: float = 0.0  # ex : montant recupere, nb candidatures envoyees
    last_run: datetime | None = None
    anomaly_count: int = 0

    @property
    def success_rate(self) -> float:
        return self.successes / self.runs if self.runs else 0.0

    @property
    def avg_duration_ms(self) -> float:
        return self.total_duration_ms / self.runs if self.runs else 0.0

    @property
    def cost_per_success(self) -> float:
        return self.total_cost_usd / self.successes if self.successes else 0.0

    @property
    def reliability_score(self) -> float:
        """Score 0-1 : 50% success rate + 50% absence d anomalies."""
        return min(1.0, self.success_rate * 0.7 + max(0, 1 - self.anomaly_count / 10) * 0.3)

    def to_dict(self) -> dict:
        return {
            "agent": self.agent_name,
            "runs": self.runs,
            "success_rate": round(self.success_rate, 3),
            "avg_duration_ms": round(self.avg_duration_ms, 1),
            "cost_per_success": round(self.cost_per_success, 4),
            "reliability_score": round(self.reliability_score, 3),
            "business_value": self.business_value,
            "anomalies": self.anomaly_count,
        }


class BusinessObservability:
    def __init__(self):
        self._lock = RLock()
        self._scores: dict[str, AgentBusinessScore] = {}
        # Sprint 3 : index secondaire (tenant_id, agent_name) -> score
        # Permet aux routes /business-dashboard et /workflows/status de filtrer
        # par tenant sans casser les consommateurs existants (qui tombent sur
        # la clee "default" quand tenant_id est omis).
        self._scores_by_tenant: dict[tuple[str, str], AgentBusinessScore] = {}

    def record_run(self, agent_name: str, success: bool, duration_ms: float,
                    cost_usd: float = 0.0, business_value: float = 0.0,
                    tenant_id: str = "default") -> None:
        with self._lock:
            s = self._scores.setdefault(agent_name, AgentBusinessScore(agent_name=agent_name))
            s.runs += 1
            if success:
                s.successes += 1
            else:
                s.failures += 1
            s.total_cost_usd += cost_usd
            s.total_duration_ms += duration_ms
            s.business_value += business_value
            s.last_run = datetime.now(timezone.utc)
            # Index tenant : on partage la meme instance
            key = (tenant_id, agent_name)
            ts = self._scores_by_tenant.setdefault(key, s)

    def record_anomaly(self, agent_name: str, tenant_id: str = "default") -> None:
        with self._lock:
            s = self._scores.setdefault(agent_name, AgentBusinessScore(agent_name=agent_name))
            s.anomaly_count += 1
            # Index tenant : on partage la meme instance
            key = (tenant_id, agent_name)
            self._scores_by_tenant.setdefault(key, s)

    def detect_anomalies(self) -> dict[str, list[str]]:
        """Detecte des anomalies simples (taux d echec eleve, agent loop, cout anormal)."""
        with self._lock:
            anomalies: dict[str, list[str]] = defaultdict(list)
            now = datetime.now(timezone.utc)
            for agent, s in self._scores.items():
                # Anomalie 1 : trop d echecs recents
                if s.runs >= 5 and s.success_rate < 0.3:
                    anomalies[agent].append("high_failure_rate")
                # Anomalie 2 : cout par succes explosif
                if s.cost_per_success > 1.0:
                    anomalies[agent].append("high_cost_per_success")
                # Anomalie 3 : agent qui tourne tres longtemps
                if s.avg_duration_ms > 60_000:
                    anomalies[agent].append("long_avg_duration")
                # Anomalie 4 : agent inactif depuis longtemps
                if s.last_run and (now - s.last_run) > timedelta(days=7):
                    anomalies[agent].append("stale")
            return dict(anomalies)

    def get_score(self, agent_name: str) -> dict | None:
        with self._lock:
            s = self._scores.get(agent_name)
            return s.to_dict() if s else None

    def dashboard_for(self, tenant_id: str) -> dict:
        """Dashboard scope par tenant : cout LLM, succes, duree, par agent."""
        with self._lock:
            agents = [
                s.to_dict() for (tid, _name), s in self._scores_by_tenant.items()
                if tid == tenant_id
            ]
        total_cost = sum(a["cost_per_success"] * a["runs"] for a in agents)
        total_runs = sum(a["runs"] for a in agents)
        total_success = sum(int(a["success_rate"] * a["runs"]) for a in agents)
        return {
            "tenant_id": tenant_id,
            "scope": "tenant_scoped",
            "total_cost_usd": round(total_cost, 4),
            "total_runs": total_runs,
            "total_success": total_success,
            "global_success_rate": round(total_success / total_runs, 3) if total_runs else 0.0,
            "agents": agents,
        }

    def dashboard(self) -> dict:
        with self._lock:
            return {
                "agents": [s.to_dict() for s in self._scores.values()],
                "anomalies": self.detect_anomalies(),
                "totals": {
                    "runs": sum(s.runs for s in self._scores.values()),
                    "cost_usd": round(sum(s.total_cost_usd for s in self._scores.values()), 4),
                    "business_value": sum(s.business_value for s in self._scores.values()),
                },
            }

    def reset(self) -> None:
        with self._lock:
            self._scores.clear()
            self._scores_by_tenant.clear()


business_observability = BusinessObservability()
