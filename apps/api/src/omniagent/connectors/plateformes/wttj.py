"""Welcome to the Jungle connector.

WTTJ n'a pas d'API publique officielle. Le site autorise un scraping raisonnable
(pas d'auth, pas de paywall) mais leur DOM change regulierement.

Cette implementation :
  - fournit une recherche en mode mock (offres representatives)
  - expose la meme signature que les autres connecteurs pour etre branche
    uniformement dans l orchestrateur Emploi
  - prepare le terrain pour un vrai scraper (Playwright headless via
    browser_service, comme LinkedIn/Indeed/HelloWork existants)

Variables d env :
  WTTJ_BASE_URL : defaut https://www.welcometothejungle.com
  WTTJ_LIVE     : '1' pour tenter le live (pas implemente ici, renvoie mock)
"""
from __future__ import annotations
import os
import logging
from typing import Any

from omniagent.connectors.base.connector import Connector


logger = logging.getLogger(__name__)


class WTTJConnector(Connector):
    name = "wttj"
    category = "plateformes"

    def __init__(self, base_url: str = "", live: bool = False):
        self._base_url = base_url or os.getenv("WTTJ_BASE_URL",
                                                "https://www.welcometothejungle.com")
        # Le live n est pas implemente : on garde mock pour eviter un scraper fragile.
        # Pour activer, mettre WTTJ_LIVE=1 et brancher le scraper (TODO).
        self._live = live or os.getenv("WTTJ_LIVE", "") == "1"

    @property
    def is_configured(self) -> bool:
        return True  # toujours dispo (mock)

    async def health_check(self) -> bool:
        return True

    async def search(self, query: str, location: str = "",
                       contract: str | None = None,
                       max_results: int = 30) -> list[dict]:
        # Pas de scraping live pour l instant. On renvoie le mock.
        return _mock_offers(query, location, contract, max_results)

    async def close(self) -> None:
        return None


def _mock_offers(query: str, location: str, contract: str | None,
                  max_results: int) -> list[dict]:
    """Offres representatives WTTJ (startups / tech FR)."""
    base = [
        {"title": "Senior Data Scientist", "company": "Alan", "location": "Paris",
         "contract": "cdi", "id": "WTTJ-MOCK-001"},
        {"title": "ML Engineer", "company": "Qonto", "location": "Paris",
         "contract": "cdi", "id": "WTTJ-MOCK-002"},
        {"title": "Data Engineer", "company": "Plaid", "location": "Paris",
         "contract": "cdi", "id": "WTTJ-MOCK-003"},
        {"title": "Staff ML Engineer", "company": "Mistral AI", "location": "Paris",
         "contract": "cdi", "id": "WTTJ-MOCK-004"},
        {"title": "Alternance Data Scientist", "company": "Swile", "location": "Paris",
         "contract": "alternance", "id": "WTTJ-MOCK-005"},
        {"title": "Senior Python Developer", "company": "Doctrine.fr", "location": "Paris",
         "contract": "cdi", "id": "WTTJ-MOCK-006"},
        {"title": "Engineering Manager Data", "company": "Pennylane", "location": "Paris",
         "contract": "cdi", "id": "WTTJ-MOCK-007"},
        {"title": "Product Engineer (Python/React)", "company": "Yousign", "location": "Paris",
         "contract": "cdi", "id": "WTTJ-MOCK-008"},
    ]
    out = []
    q = (query or "").lower()
    for o in base:
        if q and q not in o["title"].lower() and q not in o["company"].lower():
            continue
        if contract and o["contract"] != contract.lower():
            continue
        if location and location.lower() not in o["location"].lower():
            continue
        out.append({
            "title": o["title"],
            "company": o["company"],
            "location": o["location"],
            "url": f"https://www.welcometothejungle.com/companies/{o['company'].lower().replace(' ', '-')}/jobs/{o['id'].lower()}",
            "source": "wttj",
            "description": f"Recherche : {query}. Entreprise : {o['company']} (startup FR).",
            "contract": o["contract"],
            "posted_at": "2026-07-01",
            "external_id": o["id"],
            "raw": {"_mock": True, **o},
        })
        if len(out) >= max_results:
            break
    return out
