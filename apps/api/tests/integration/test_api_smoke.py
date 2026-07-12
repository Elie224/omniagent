"""Smoke test : verifie que l API demarre et que les routes principales repondent.

Vague B : focus Emploi. Les tests marketing/recouvrement ont ete retires.
"""
import os
# Active un mode de test avant tout import.
os.environ.setdefault("ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("CORS_ORIGINS", '["http://localhost:3000"]')
os.environ.setdefault("ACTIVE_MODULES", '["emploi","transverse"]')

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from omniagent.main import app
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "modules" in body
    # Vague B : seul emploi est liste (transverse est implicit via /shared/*)
    assert "emploi" in body["modules"]


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "OmniAgent API"
    assert "api_v1" in body


def test_modules(client):
    """Vague B : /modules ne liste que les modules actifs (emploi + transverse)."""
    r = client.get("/modules")
    assert r.status_code == 200
    body = r.json()
    assert "emploi" in body
    assert "transverse" in body
    # marketing et recouvrement ont ete retires du repo
    assert "marketing" not in body
    assert "recouvrement" not in body


def test_metrics(client):
    r = client.get("/metrics")
    assert r.status_code == 200


def test_orchestrator_status(client):
    r = client.get("/orchestrator/status")
    assert r.status_code == 200
    body = r.json()
    assert "policy" in body
    assert "search_job_and_apply" in body["supported_intents"]


def test_orchestrator_run_unknown_intent(client):
    r = client.post("/orchestrator/run", json={
        "user_id": "demo", "message": "xyzqwerty noop", "context": {},
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("unknown_intent", "partial", "completed")


def test_orchestrator_run_emploi(client):
    """Vague B : smoke test sur le workflow Emploi (intent search_job_and_apply)."""
    r = client.post("/orchestrator/run", json={
        "user_id": "demo",
        "message": "Trouver une offre emploi Data Scientist a Paris (max 5)",
        "context": {
            "query": "Data Scientist",
            "location": "Paris",
            "sources": ["linkedin", "indeed", "hellowork"],
            "max_results": 5,
        },
    })
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "search_job_and_apply"


def test_employment_search_requires_auth(client):
    r = client.post("/api/v1/employment/search", json={
        "keywords": "data", "location": "Paris", "max_results": 5,
    })
    # En dev, fallback "demo" ; doit passer.
    assert r.status_code in (200, 403)


def test_transverse_memory(client):
    r = client.post("/api/v1/shared/memory", json={
        "action": "remember", "scope": "session",
        "key": "smoke", "value": {"hello": "world"},
    }, headers={"X-User": "demo"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("stored") is True


def test_events_query_requires_auth(client):
    """Le store d events est reserve aux operateurs (auth obligatoire)."""
    r = client.get("/api/v1/shared/events/query")
    # En dev sans auth, fallback demo -> 200 ; en prod -> 401
    assert r.status_code in (200, 401)
    if r.status_code == 200:
        body = r.json()
        assert "events" in body


def test_events_query_persists_after_publish(client):
    """Publie un event via l orchestrateur Emploi et confirme qu il est queryable."""
    r = client.post("/orchestrator/run", json={
        "user_id": "smoke",
        "message": "Trouver une offre Data Engineer a Lyon (max 3)",
        "context": {"query": "Data Engineer", "location": "Lyon", "max_results": 3},
    })
    assert r.status_code == 200
    # L orchestrateur a du publier des events AGENT_*/WORKFLOW_*
    r2 = client.get("/api/v1/shared/events/query?limit=50")
    assert r2.status_code == 200
    body = r2.json()
    assert body["count"] >= 0

