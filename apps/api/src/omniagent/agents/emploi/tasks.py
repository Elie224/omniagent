"""Taches Celery du module Emploi."""
from omniagent.core.celery_app import celery_app


@celery_app.task(name="emploi.search_and_apply")
def search_and_apply(user_id: str, criteria: dict) -> dict:
    return {"user_id": user_id, "criteria": criteria, "status": "scheduled"}


@celery_app.task(name="emploi.tailor_cv")
def tailor_cv(user_id: str, offer_id: str) -> dict:
    return {"user_id": user_id, "offer_id": offer_id, "status": "generating"}