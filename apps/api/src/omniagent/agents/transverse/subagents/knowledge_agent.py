"""Knowledge Agent : recherche semantique dans les documents utilisateur (RAG)."""
from __future__ import annotations
import re
from typing import Any


class KnowledgeAgent:
    """Indexe et retrouve des documents (CV, lettres, offres, factures, PDFs).
    Utilise la memoire vectorielle + fallback BM25 si pas d''embedding."""

    def __init__(self, memory_agent):
        self._memory = memory_agent
        self._index: dict[str, list[dict]] = {
            "cv": [], "lettre": [], "offre": [], "facture": [],
            "contrat": [], "autre": [],
        }

    def index_document(self, doc_id: str, doc_type: str, text: str,
                       metadata: dict | None = None) -> dict:
        if doc_type not in self._index:
            doc_type = "autre"
        doc = {"id": doc_id, "type": doc_type, "text": text,
               "metadata": metadata or {}, "tokens": self._tokenize(text)}
        self._index[doc_type].append(doc)
        # Memorise dans la memoire vectorielle (cle = type:id)
        self._memory.remember("vector", f"{doc_type}:{doc_id}",
                              {"text": text[:500], "metadata": metadata or {}})
        return {"indexed": doc_id, "type": doc_type, "tokens": len(doc["tokens"])}

    def search(self, query: str, doc_types: list[str] | None = None,
               top_k: int = 5) -> list[dict]:
        q_tokens = set(self._tokenize(query))
        scores: list[tuple[float, dict]] = []
        types = doc_types or list(self._index.keys())
        for t in types:
            for doc in self._index.get(t, []):
                overlap = len(q_tokens & set(doc["tokens"]))
                if overlap == 0:
                    continue
                score = overlap / max(len(q_tokens), 1)
                scores.append((score, doc))
        scores.sort(key=lambda x: -x[0])
        return [
            {"id": d["id"], "type": d["type"], "score": s,
             "snippet": d["text"][:300], "metadata": d["metadata"]}
            for s, d in scores[:top_k]
        ]

    def get(self, doc_id: str, doc_type: str | None = None) -> dict | None:
        if doc_type:
            docs = self._index.get(doc_type, [])
            for d in docs:
                if d["id"] == doc_id:
                    return d
        else:
            for t, docs in self._index.items():
                for d in docs:
                    if d["id"] == doc_id:
                        return d
        return None

    def list_by_type(self, doc_type: str) -> list[dict]:
        return [d for d in self._index.get(doc_type, [])]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"\w+", text.lower())


_knowledge_agent: KnowledgeAgent | None = None


def get_knowledge_agent() -> KnowledgeAgent:
    global _knowledge_agent
    if _knowledge_agent is None:
        from omniagent.agents.transverse.subagents.memory_agent import get_memory_agent
        _knowledge_agent = KnowledgeAgent(get_memory_agent())
    return _knowledge_agent


async def run(input_data: dict, user_id: str) -> dict:
    action = input_data.get("action", "search")
    agent = get_knowledge_agent()
    if action == "index":
        return agent.index_document(
            doc_id=input_data["doc_id"], doc_type=input_data.get("doc_type", "autre"),
            text=input_data["text"], metadata=input_data.get("metadata"),
        )
    if action == "get":
        return {"document": agent.get(input_data["doc_id"], input_data.get("doc_type"))}
    if action == "list":
        return {"documents": agent.list_by_type(input_data["doc_type"])}
    return {"results": agent.search(input_data.get("query", ""),
                                    input_data.get("doc_types"),
                                    input_data.get("top_k", 5))}
