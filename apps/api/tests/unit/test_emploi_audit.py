from fastapi.testclient import TestClient


class _FakeAudit:
    calls = []

    def __init__(self, db_session=None):
        self.db_session = db_session

    async def alog(self, user_id, action, payload=None, tenant_id="default", ip=None):
        _FakeAudit.calls.append(
            {
                "user_id": user_id,
                "action": str(action),
                "payload": payload or {},
                "tenant_id": tenant_id,
                "ip": ip,
            }
        )

    async def history(self, tenant_id="default", user_id=None, limit=100):
        return [{"id": "a1", "tenant_id": tenant_id, "user_id": user_id or "demo", "action": "agent_run", "payload": {}, "ip": None, "timestamp": "2026-01-01T00:00:00+00:00"}]


def test_contact_enrich_reject_without_confirmation_is_audited(monkeypatch):
    from omniagent.main import app
    from omniagent.agents.emploi import router as emploi_router

    _FakeAudit.calls = []
    monkeypatch.setattr(emploi_router, "AuditLog", _FakeAudit)

    client = TestClient(app)
    r = client.post(
        "/api/v1/employment/contact/enrich",
        json={"offer": {"title": "Data Scientist"}, "company": "ACME", "user_confirmation": False, "legal_basis": "legitimate_interest"},
        headers={"X-User": "demo", "X-Role": "user"},
    )
    assert r.status_code == 422
    assert _FakeAudit.calls, "Audit should be written on rejected contact enrichment"
    assert _FakeAudit.calls[-1]["payload"]["reason"] == "missing_user_confirmation"


def test_audit_history_endpoint(monkeypatch):
    from omniagent.main import app
    from omniagent.agents.emploi import router as emploi_router

    monkeypatch.setattr(emploi_router, "AuditLog", _FakeAudit)
    client = TestClient(app)
    r = client.get(
        "/api/v1/employment/audit/history?limit=10",
        headers={"X-User": "demo", "X-Role": "user"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert isinstance(body["items"], list)
