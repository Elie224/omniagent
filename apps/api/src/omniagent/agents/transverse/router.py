"""Routes API v1 du module transverse (5 agents)."""
from fastapi import APIRouter, Depends
from omniagent.auth.dependencies import CurrentUser, get_current_user
from pydantic import BaseModel, Field
from typing import Literal

from omniagent.agents.transverse.subagents.memory_agent import run as memory_run
from omniagent.agents.transverse.subagents.knowledge_agent import run as knowledge_run
from omniagent.agents.transverse.subagents.monitoring_agent import run as monitoring_run
from omniagent.agents.transverse.subagents.planning_agent import run as planning_run
from omniagent.agents.transverse.subagents.notification_agent import run as notification_run


router = APIRouter()


# ---------------- Memory ----------------
class MemoryRequest(BaseModel):
    action: Literal["remember", "recall", "search", "add_exclusion"] = "recall"
    scope: Literal["session", "user", "vector", "domain"] = "session"
    key: str = ""
    value: object | None = None
    query: str = ""
    top_k: int = Field(default=5, ge=1, le=50)
    ttl_seconds: int | None = None


@router.post("/memory")
async def memory(
    req: MemoryRequest,
    user: CurrentUser = Depends(get_current_user),
):
    return await memory_run(req.model_dump(), user_id=user.user_id)


# ---------------- Knowledge ----------------
class KnowledgeRequest(BaseModel):
    action: Literal["index", "search", "get", "list"] = "search"
    doc_id: str = ""
    doc_type: Literal["cv", "lettre", "offre", "facture", "contrat", "autre"] = "autre"
    text: str = ""
    query: str = ""
    doc_types: list[str] | None = None
    top_k: int = 5
    metadata: dict | None = None


@router.post("/knowledge")
async def knowledge(
    req: KnowledgeRequest,
    user: CurrentUser = Depends(get_current_user),
):
    return await knowledge_run(req.model_dump(), user_id=user.user_id)


# ---------------- Monitoring ----------------
class MonitoringRequest(BaseModel):
    action: Literal["record", "error_rate", "zombies", "retry", "snapshot"] = "snapshot"
    agent_name: str = ""
    status: str = "success"
    run_id: str = ""
    error: str | None = None
    retry_count: int = 0
    payload: dict = Field(default_factory=dict)


@router.post("/monitoring")
async def monitoring(
    req: MonitoringRequest,
    user: CurrentUser = Depends(get_current_user),
):
    return await monitoring_run(req.model_dump(), user_id=user.user_id)


# ---------------- Planning ----------------
class PlanningRequest(BaseModel):
    action: Literal["schedule", "cancel", "tick", "list"] = "list"
    task_id: str = ""
    agent_name: str = ""
    payload: dict = Field(default_factory=dict)
    frequency: Literal["once", "hourly", "daily", "weekly", "monthly"] = "daily"
    start_at: str | None = None


@router.post("/planning")
async def planning(
    req: PlanningRequest,
    user: CurrentUser = Depends(get_current_user),
):
    return await planning_run(req.model_dump(), user_id=user.user_id)


# ---------------- Notification ----------------
class NotificationRequest(BaseModel):
    action: Literal["send", "bulk", "history"] = "send"
    title: str = ""
    body: str = ""
    channel: Literal["email", "push", "slack", "in_app", "sms", "whatsapp"] = "in_app"
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    user_ids: list[str] | None = None
    metadata: dict | None = None
    limit: int = 20


@router.post("/notification")
async def notification(
    req: NotificationRequest,
    user: CurrentUser = Depends(get_current_user),
):
    return await notification_run(req.model_dump(), user_id=user.user_id)


@router.get("/health")
async def health():
    return {"module": "transverse", "status": "ok",
            "agents": ["agent_memory", "agent_knowledge",
                       "agent_monitoring", "agent_planning",
                       "agent_notification"]}