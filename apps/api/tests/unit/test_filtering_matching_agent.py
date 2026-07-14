import pytest

from omniagent.agents.emploi.subagents import filtering_matching_agent as agent


@pytest.mark.asyncio
async def test_filtering_matching_keeps_only_city_and_threshold():
    offers = [
        {
            "offer_id": "1",
            "title": "Data Scientist Python",
            "company": "ACME",
            "location": "Paris",
            "contract": "CDI",
            "description": "Machine learning, python, NLP",
            "posted_at": "2099-01-01T10:00:00Z",
        },
        {
            "offer_id": "2",
            "title": "Comptable",
            "company": "BETA",
            "location": "Lyon",
            "contract": "CDI",
            "description": "Comptabilite generale",
            "posted_at": "2099-01-01T10:00:00Z",
        },
    ]
    profile = {
        "skills": ["python", "machine learning", "nlp"],
        "target_roles": ["Data Scientist"],
        "city": "Paris",
    }

    out = await agent.run(
        {
            "offers": offers,
            "city": "Paris",
            "radius": "city",
            "contract": "emploi",
            "recency_hours": 24 * 365,
            "score_threshold": 0.40,
            "max_results": 20,
            "profile": profile,
        },
        user_id="u1",
    )

    produced = out["outputs_produced"]
    assert out["status"] == "ok"
    assert produced["count_input"] == 2
    assert produced["count_kept"] == 1
    assert produced["offers"][0]["offer_id"] == "1"


@pytest.mark.asyncio
async def test_filtering_matching_rejects_old_offers():
    offers = [
        {
            "offer_id": "1",
            "title": "Data Scientist",
            "company": "ACME",
            "location": "Paris",
            "contract": "CDI",
            "description": "python data",
            "posted_at": "2000-01-01T10:00:00Z",
        }
    ]

    out = await agent.run(
        {
            "offers": offers,
            "city": "Paris",
            "radius": "city",
            "contract": "emploi",
            "recency_hours": 24,
            "score_threshold": 0.0,
            "max_results": 20,
            "profile": {"skills": ["python"], "target_roles": ["data scientist"]},
        },
        user_id="u1",
    )

    produced = out["outputs_produced"]
    assert produced["count_kept"] == 0
    assert produced["rejected"]["recency"] == 1


@pytest.mark.asyncio
async def test_filtering_matching_deduplicates_cross_source_offers():
    offers = [
        {
            "offer_id": "ft-1",
            "title": "Data Scientist",
            "company": "ACME",
            "location": "Paris",
            "contract": "CDI",
            "description": "python ml",
            "posted_at": "2099-01-01T10:00:00Z",
            "source": "france_travail",
        },
        {
            "offer_id": "adz-1",
            "title": "Data Scientist",
            "company": "ACME",
            "location": "Paris",
            "contract": "CDI",
            "description": "python ml",
            "posted_at": "2099-01-01T10:00:00Z",
            "source": "adzuna",
        },
    ]

    out = await agent.run(
        {
            "offers": offers,
            "city": "Paris",
            "radius": "city",
            "contract": "emploi",
            "recency_hours": 24,
            "score_threshold": 0.0,
            "max_results": 20,
            "profile": {"skills": ["python"], "target_roles": ["data scientist"]},
        },
        user_id="u1",
    )

    produced = out["outputs_produced"]
    assert produced["count_input"] == 2
    assert produced["duplicates_removed"] == 1
    assert produced["count_after_dedup"] == 1
