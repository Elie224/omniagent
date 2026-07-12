"""Configuration Celery pour taches asynchrones."""
from celery import Celery

from omniagent.core.config import settings

celery_app = Celery(
    "omniagent",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "omniagent.agents.recouvrement.tasks",
        "omniagent.agents.emploi.tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Paris",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
)