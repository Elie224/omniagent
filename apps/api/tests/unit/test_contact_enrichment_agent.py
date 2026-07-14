import pytest

from omniagent.agents.emploi.subagents.contact_enrichment_agent import run


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
