"""Tests des agents du module Emploi."""
import pytest


@pytest.mark.asyncio
async def test_coordinator_emploi_dispatches():
    from omniagent.agents.emploi.subagents.coordinator import run
    r = await run({"criteria": {"keywords": "data scientist"}}, "u1")
    assert "agent_linkedin" in r["dispatched"]
    assert "agent_indeed" in r["dispatched"]
    assert "agent_hellowork" in r["dispatched"]


@pytest.mark.asyncio
async def test_lettre_generation():
    from omniagent.agents.emploi.subagents.lettre_agent import run
    r = await run({"contract": "alternance",
                   "variables": {"rh_name": "M. Dupont", "role": "data scientist",
                                 "company": "ACME", "name": "Jean",
                                 "formation": "M2 Data", "motivation": "votre stack"}}, "u1")
    assert "M. Dupont" in r["body"]
    assert "data scientist" in r["body"]
    assert r["contract"] == "alternance"