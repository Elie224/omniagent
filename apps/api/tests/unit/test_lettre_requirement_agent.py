import pytest

from omniagent.agents.emploi.subagents.lettre_requirement_agent import run


@pytest.mark.asyncio
async def test_lettre_requirement_generates_when_offer_requires_letter():
    out = await run(
        {
            "offer": {
                "title": "Data Scientist",
                "company": "ACME",
                "description": "Merci de joindre votre lettre de motivation a votre candidature.",
            },
            "profile": {"full_name": "Alice Martin", "formation": "Master IA"},
        },
        user_id="u1",
    )

    assert out["status"] == "generated"
    produced = out["outputs_produced"]
    assert produced["required"] is True
    assert produced["letter"] is not None
    assert "ACME" in produced["letter"]["body"]


@pytest.mark.asyncio
async def test_lettre_requirement_skips_when_not_required():
    out = await run(
        {
            "offer": {
                "title": "Data Scientist",
                "company": "ACME",
                "description": "Postulez directement via le lien annonceur.",
            },
            "profile": {"full_name": "Alice Martin"},
        },
        user_id="u1",
    )

    assert out["status"] == "skipped_not_required"
    produced = out["outputs_produced"]
    assert produced["required"] is False
    assert produced["letter"] is None
