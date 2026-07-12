"""Tests d''integration : startup de l''API et healthcheck.

Vague B : focus Emploi uniquement. Les healthchecks marketing/finance ont ete retires.
"""
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fastapi.testclient import TestClient
from omniagent.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "modules" in data


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["name"] == "OmniAgent API"


def test_modules_list(client):
    """Vague B : seul Emploi est actif. /modules ne liste que les modules actifs."""
    r = client.get("/modules")
    assert r.status_code == 200
    modules = r.json()
    assert "emploi" in modules
    assert "transverse" in modules
    # marketing et recouvrement ont ete retires du repo
    assert "marketing" not in modules
    assert "recouvrement" not in modules


def test_module_health_endpoints(client):
    """Vague B : seul /api/v1/employment/health doit etre monte."""
    r = client.get("/api/v1/employment/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    # Les anciens endpoints marketing/finance sont retires (404 attendu)
    for path in ("/api/v1/marketing/health", "/api/v1/finance/health"):
        r = client.get(path)
        assert r.status_code == 404, f"{path} devrait etre retire, got {r.status_code}"