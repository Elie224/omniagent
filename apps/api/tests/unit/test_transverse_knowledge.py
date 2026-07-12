"""Tests du Knowledge Agent (RAG)."""
import pytest


@pytest.mark.asyncio
async def test_knowledge_index_and_search():
    from omniagent.agents.transverse.subagents.knowledge_agent import get_knowledge_agent, run
    agent = get_knowledge_agent()
    agent._index = {k: [] for k in agent._index}  # reset

    await run({"action": "index", "doc_id": "cv1", "doc_type": "cv",
               "text": "Experienced Python developer with FastAPI and LangChain skills.",
               "metadata": {"name": "Alice"}}, "u1")
    await run({"action": "index", "doc_id": "offre1", "doc_type": "offre",
               "text": "Looking for a data scientist with Python and SQL experience.",
               "metadata": {"company": "ACME"}}, "u1")

    r = await run({"action": "search", "query": "Python developer"}, "u1")
    results = r["results"]
    assert len(results) >= 1
    assert any(res["type"] == "cv" for res in results)


@pytest.mark.asyncio
async def test_knowledge_search_filters_by_type():
    from omniagent.agents.transverse.subagents.knowledge_agent import get_knowledge_agent, run
    agent = get_knowledge_agent()
    agent._index = {k: [] for k in agent._index}

    await run({"action": "index", "doc_id": "f1", "doc_type": "facture",
               "text": "Facture 1234 - 5000 euros - client ACME", "metadata": {}}, "u1")
    await run({"action": "index", "doc_id": "cv1", "doc_type": "cv",
               "text": "CV de Bob, developpeur fullstack JavaScript", "metadata": {}}, "u1")

    r = await run({"action": "search", "query": "facture",
                   "doc_types": ["facture"]}, "u1")
    assert all(res["type"] == "facture" for res in r["results"])


@pytest.mark.asyncio
async def test_knowledge_list_by_type():
    from omniagent.agents.transverse.subagents.knowledge_agent import get_knowledge_agent, run
    agent = get_knowledge_agent()
    agent._index = {k: [] for k in agent._index}

    await run({"action": "index", "doc_id": "cv1", "doc_type": "cv",
               "text": "CV 1", "metadata": {}}, "u1")
    await run({"action": "index", "doc_id": "cv2", "doc_type": "cv",
               "text": "CV 2", "metadata": {}}, "u1")
    r = await run({"action": "list", "doc_type": "cv"}, "u1")
    assert len(r["documents"]) == 2