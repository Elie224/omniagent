"""Tests de la regle auth stricte en production.

Garantit que les headers legacy X-User/X-Role sont REJETES en env=production,
meme si allow_legacy_headers=True (defense en profondeur contre l usurpation
d identite en prod).

En dev/test, le comportement legacy reste valide pour faciliter les tests E2E
et le developpement local.
"""
import os
import importlib
import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient


@pytest.fixture
def fresh_app(monkeypatch):
    """App minimale qui depend de get_current_user, avec un settings isole."""
    # Forcer env=production pour ce test
    monkeypatch.setenv("ENV", "production")
    # Recharger le module settings pour prendre en compte la nouvelle env
    import omniagent.core.config as cfg
    importlib.reload(cfg)
    # Recharger dependencies pour qu il importe le settings frais
    import omniagent.auth.dependencies as deps
    importlib.reload(deps)

    app = FastAPI()

    @app.get("/whoami")
    async def whoami(user=Depends(deps.get_current_user)):
        return {"user_id": user.user_id}

    yield app, deps
    # Cleanup : revenir en dev pour les tests suivants
    monkeypatch.setenv("ENV", "development")
    importlib.reload(cfg)
    importlib.reload(deps)


def test_prod_rejects_legacy_x_user(fresh_app):
    """En production, X-User ne doit PAS authentifier (meme si allow_legacy=True)."""
    app, _deps = fresh_app
    with TestClient(app) as c:
        r = c.get("/whoami", headers={"X-User": "alice", "X-Role": "admin"})
        assert r.status_code == 401, (
            f"En prod, X-User doit etre rejete. Got {r.status_code} {r.text}"
        )


def test_prod_rejects_no_header(fresh_app):
    """En production, aucun header -> 401 (pas de fallback demo)."""
    app, _deps = fresh_app
    with TestClient(app) as c:
        r = c.get("/whoami")
        assert r.status_code == 401


def test_dev_accepts_legacy_x_user():
    """En dev, X-User reste un mode d auth valide (ne casse pas les tests E2E)."""
    os.environ["ENV"] = "development"
    import omniagent.core.config as cfg
    importlib.reload(cfg)
    import omniagent.auth.dependencies as deps
    importlib.reload(deps)

    app = FastAPI()

    @app.get("/whoami")
    async def whoami(user=Depends(deps.get_current_user)):
        return {"user_id": user.user_id, "is_legacy": user.is_legacy}

    with TestClient(app) as c:
        r = c.get("/whoami", headers={"X-User": "alice", "X-Role": "admin"})
        assert r.status_code == 200
        assert r.json()["user_id"] == "alice"
        assert r.json()["is_legacy"] is True