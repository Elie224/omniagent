import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from omniagent.main import app
    with TestClient(app) as c:
        yield c


def test_orchestrator_workflow_blocks_legacy_job_search_dag(client):
    r = client.post(
        "/orchestrator/workflow",
        json={"workflow": "job_search_dag", "dry_run": True, "context": {}},
        headers={"X-User": "demo", "X-Role": "admin"},
    )
    assert r.status_code == 403
    assert "legacy" in r.json().get("detail", "")


def test_orchestrator_workflow_forces_dry_run(client):
    r = client.post(
        "/orchestrator/workflow",
        json={"workflow": "intent_research", "dry_run": False, "context": {}},
        headers={"X-User": "demo", "X-Role": "admin"},
    )
    assert r.status_code == 403
    assert "dry_run=true" in r.json().get("detail", "")
