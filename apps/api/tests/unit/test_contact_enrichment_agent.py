import pytest

from omniagent.agents.emploi.subagents.contact_enrichment_agent import run, _is_safe_public_url


@pytest.mark.asyncio
async def test_contact_enrichment_extracts_contacts_from_offer_description():
    out = await run(
        {
            "offer": {
                "company": "ACME",
                "description": "Contact recrutement: jobs@acme.fr - Tel: 01 23 45 67 89",
            }
        },
        user_id="u1",
    )

    assert out["status"] == "ok"
    produced = out["outputs_produced"]
    assert "jobs@acme.fr" in (produced.get("emails") or [])
    assert any(p.endswith("123456789") for p in (produced.get("phones") or []))


@pytest.mark.asyncio
async def test_contact_enrichment_no_company_returns_no_company_status():
    out = await run({"offer": {}}, user_id="u1")

    assert out["status"] == "no_company"
    produced = out["outputs_produced"]
    assert produced["emails"] == []
    assert produced["phones"] == []


def test_contact_enrichment_rejects_localhost_url():
    assert _is_safe_public_url("https://localhost/admin") is False


def test_contact_enrichment_accepts_public_https_with_public_dns(monkeypatch):
    from omniagent.agents.emploi.subagents import contact_enrichment_agent as mod

    def _fake_getaddrinfo(host, port, proto=None):
        return [(None, None, None, None, ("93.184.216.34", port))]

    monkeypatch.setattr(mod.socket, "getaddrinfo", _fake_getaddrinfo)
    assert _is_safe_public_url("https://example.com/jobs") is True
