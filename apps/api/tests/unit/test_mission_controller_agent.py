import pytest

from omniagent.agents.emploi.subagents import mission_controller_agent as agent


@pytest.mark.asyncio
async def test_mission_controller_runs_filtering_and_returns_offers():
    offers = [
        {
            "offer_id": "o1",
            "title": "Data Scientist Python",
            "company": "ACME",
            "location": "Paris",
            "contract": "CDI",
            "description": "python machine learning",
            "posted_at": "2099-01-01T10:00:00Z",
        }
    ]

    out = await agent.run(
        {
            "mission": {"query": "data scientist", "location": "Paris"},
            "criteria": {
                "location": "Paris",
                "city": "Paris",
                "radius": "city",
                "contract": "emploi",
                "recency_hours": 24,
                "max_results": 20,
                "score_threshold": 0.2,
            },
            "offers": offers,
            "profile": {"skills": ["python", "machine learning"], "target_roles": ["data scientist"]},
            "options": {
                "run_contact_enrichment": False,
                "run_letter_generation": False,
                "run_application_send": False,
            },
        },
        user_id="u1",
    )

    assert out["agent"] == "agent_mission_controller"
    assert out["status"] == "completed"
    produced = out["outputs_produced"]
    assert produced["summary"]["offers_count"] == 1
    assert produced["summary"]["steps_failed"] == 0


@pytest.mark.asyncio
async def test_mission_controller_partial_failure(monkeypatch):
    async def _boom(*args, **kwargs):
        raise RuntimeError("simulated filtering failure")

    monkeypatch.setattr(agent, "run_filtering_matching", _boom)

    out = await agent.run(
        {
            "mission": {"query": "data scientist", "location": "Paris"},
            "criteria": {"location": "Paris", "max_results": 20, "score_threshold": 0.2},
            "offers": [
                {
                    "offer_id": "o1",
                    "title": "Data Scientist",
                    "company": "ACME",
                    "location": "Paris",
                    "description": "python",
                    "posted_at": "2099-01-01T10:00:00Z",
                }
            ],
            "options": {
                "run_contact_enrichment": False,
                "run_letter_generation": False,
                "run_application_send": False,
            },
        },
        user_id="u1",
    )

    assert out["status"] == "completed_with_partial_failures"
    failures = out["outputs_produced"]["partial_failures"]
    assert any(f["step"] == "filtering_matching" for f in failures)
