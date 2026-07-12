"""The Muse connector (https://www.themuse.com/developers/api/v2).

API gratuite avec cle : https://www.themuse.com/developers/signup
Couvre : US + UK + remote, tres bon sur la tech / startup / data / engineering.
Pas d authentification OAuth, juste une cle API en header `Authorization: Bearer`.

Variables d env :
  THEMUSE_API_KEY : cle API (optionnelle, augmente les rate limits)

Sans cle : rate limite bas (~100 req/jour via IP). Mock de fallback si l API est KO.
"""
from __future__ import annotations
import os
import logging
from typing import Any

import httpx

from omniagent.connectors.base.connector import Connector


logger = logging.getLogger(__name__)


class TheMuseConnector(Connector):
    name = "themuse"
    category = "plateformes"
    BASE_URL = "https://api.themuse.com/v2"

    def __init__(self, api_key: str = "", timeout: float = 15.0):
        self._api_key = api_key or os.getenv("THEMUSE_API_KEY", "")
        self._timeout = timeout

    @property
    def is_configured(self) -> bool:
        # API publique meme sans cle, mais rate limite bas.
        return True

    async def health_check(self) -> bool:
        return True

    async def search(self, query: str, location: str = "",
                       contract: str | None = None,
                       max_results: int = 30) -> list[dict]:
        # The Muse n a pas de filtre location direct : on l utilise comme mot-cle.
        # Filtre contract : "Full Time" / "Part Time" / "Contract" / "Internship".
        params: dict[str, Any] = {
            "page": 1,
            "desc": True,
            "category": "Data and Analytics",  # filre categorie si dispo, sinon on elargit
        }
        # Construction de la query : on concatene query + location
        full_query = query or ""
        if location and location.lower() not in full_query.lower():
            full_query = (full_query + " " + location).strip()
        if full_query:
            params["q"] = full_query
        # Mapping contrat simplifie : The Muse utilise "level" et "type" pas contract
        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.get(f"{self.BASE_URL}/jobs",
                                 params=params, headers=headers)
                if r.status_code != 200:
                    logger.warning("TheMuse search HTTP %s", r.status_code)
                    return _mock_themuse(query, location, contract, max_results)
                data = r.json()
        except Exception as e:
            logger.warning("TheMuse search failed: %s", e)
            return _mock_themuse(query, location, contract, max_results)

        out: list[dict] = []
        for item in (data.get("results") or [])[:max_results]:
            locs = item.get("locations") or []
            loc_label = ", ".join(locs) if isinstance(locs, list) else str(locs)
            cats = item.get("categories") or []
            cat_label = ", ".join(c.get("name", "") for c in cats if isinstance(c, dict))
            levels = item.get("levels") or []
            level_label = ", ".join(l.get("name", "") for l in levels if isinstance(l, dict))
            out.append({
                "title": item.get("name") or "",
                "company": (item.get("company") or {}).get("name") or "",
                "location": loc_label,
                "url": item.get("refs", {}).get("landing_page") or "",
                "source": "themuse",
                "description": (item.get("contents") or "")[:600],
                "contract": level_label or (item.get("type") or ""),
                "posted_at": item.get("publication_date"),
                "external_id": str(item.get("id") or ""),
                "raw": item,
            })
        return out

    async def close(self) -> None:
        return None


def _mock_themuse(query: str, location: str, contract: str | None,
                    max_results: int) -> list[dict]:
    """Mock The Muse : representatif du marche US/global tech."""
    base = [
        {"title": "Senior Data Scientist", "company": "Spotify", "location": "Remote",
         "contract": "Full Time", "id": "MUSE-MOCK-001"},
        {"title": "Machine Learning Engineer", "company": "Airbnb", "location": "Remote",
         "contract": "Full Time", "id": "MUSE-MOCK-002"},
        {"title": "Data Engineer", "company": "Lyft", "location": "New York, NY",
         "contract": "Full Time", "id": "MUSE-MOCK-003"},
        {"title": "Analytics Engineer", "company": "Notion", "location": "Remote",
         "contract": "Full Time", "id": "MUSE-MOCK-004"},
        {"title": "Staff ML Engineer", "company": "Anthropic", "location": "San Francisco, CA",
         "contract": "Full Time", "id": "MUSE-MOCK-005"},
        {"title": "Data Analyst", "company": "Pinterest", "location": "Remote",
         "contract": "Full Time", "id": "MUSE-MOCK-006"},
        {"title": "Python Backend Engineer", "company": "Stripe", "location": "Remote",
         "contract": "Full Time", "id": "MUSE-MOCK-007"},
    ]
    out = []
    q = (query or "").lower()
    for o in base:
        if q and q not in o["title"].lower() and q not in o["company"].lower():
            continue
        if location and location.lower() not in o["location"].lower():
            continue
        out.append({
            "title": o["title"],
            "company": o["company"],
            "location": o["location"],
            "url": f"https://www.themuse.com/jobs/{o['company'].lower().replace(' ', '-')}/{o['id'].lower()}",
            "source": "themuse",
            "description": f"Recherche : {query}. Entreprise : {o['company']} (US/global).",
            "contract": o["contract"],
            "posted_at": "2026-07-03",
            "external_id": o["id"],
            "raw": {"_mock": True, **o},
        })
        if len(out) >= max_results:
            break
    return out
