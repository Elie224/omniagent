"""Adzuna API connector (https://developer.adzuna.com/).

Agregateur d'offres FR + UK + US + ~16 pays. Plan gratuit : 250-1000 calls/mois
selon pays. Pas de scraping, API REST propre.

Cle API : https://developer.adzuna.com/signup (5 min).
Variables d env :
  ADZUNA_APP_ID      : app_id fournie a l inscription
  ADZUNA_API_KEY     : api_key fournie a l inscription
  ADZUNA_COUNTRY     : code pays (defaut 'fr')

Endpoint recherche : GET https://api.adzuna.com/v1/api/jobs/{country}/search/1
Docs : https://developer.adzuna.com/docs/search
"""
from __future__ import annotations
import os
import logging
from typing import Any

import httpx

from omniagent.connectors.base.connector import Connector


logger = logging.getLogger(__name__)


class AdzunaConnector(Connector):
    name = "adzuna"
    category = "plateformes"
    BASE_URL = "https://api.adzuna.com/v1/api/jobs"

    def __init__(self, app_id: str = "", api_key: str = "",
                 country: str = "fr", timeout: float = 15.0):
        self._app_id = app_id or os.getenv("ADZUNA_APP_ID", "")
        self._api_key = api_key or os.getenv("ADZUNA_API_KEY", "")
        self._country = country or os.getenv("ADZUNA_COUNTRY", "fr")
        self._timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self._app_id and self._api_key)

    async def health_check(self) -> bool:
        if not self.is_configured:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.get(
                    f"{self.BASE_URL}/{self._country}/search/1",
                    params={
                        "app_id": self._app_id,
                        "app_key": self._api_key,
                        "results_per_page": 1,
                        "what": "test",
                    },
                )
                return r.status_code == 200
        except Exception as e:
            logger.warning("adzuna health_check failed: %s", e)
            return False

    async def search(self, query: str, location: str = "",
                       contract: str | None = None,
                       max_days_old: int | None = None,
                       max_results: int = 30) -> list[dict]:
        """Recherche d'offres. Renvoie une liste normalisee compatible JobPost."""
        if not self.is_configured:
            return []
        params: dict[str, Any] = {
            "app_id": self._app_id,
            "app_key": self._api_key,
            "results_per_page": min(max_results, 50),
            "what": query,
            "what_or": query,
            "what_and": "",
            "what_phrase": "",
            "what_not": "",
            "content-type": "application/json",
        }
        if location:
            params["where"] = location
        if contract:
            # Adzuna utilise full_time / part_time / contract / permanent
            mapping = {"cdi": "permanent", "cdd": "contract", "stage": "contract", "alternance": "contract"}
            params["full_time"] = 1 if mapping.get(contract) == "permanent" else 0
            params["contract"] = 1 if mapping.get(contract) == "contract" else 0
        if max_days_old:
            params["max_days_old"] = max_days_old
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.get(f"{self.BASE_URL}/{self._country}/search/1",
                                 params=params)
                if r.status_code != 200:
                    logger.warning("adzuna search HTTP %s: %s",
                                    r.status_code, r.text[:200])
                    return []
                data = r.json()
        except Exception as e:
            logger.warning("adzuna search failed: %s", e)
            return []

        out: list[dict] = []
        for item in (data.get("results") or []):
            out.append({
                "title": item.get("title") or "",
                "company": (item.get("company") or {}).get("display_name") or "",
                "location": (item.get("location") or {}).get("display_name") or "",
                "url": item.get("redirect_url") or "",
                "source": "adzuna",
                "description": (item.get("description") or "")[:600],
                "salary": _format_salary(item.get("salary_min"), item.get("salary_max")),
                "contract": (item.get("contract_type") or "").lower() or None,
                "posted_at": item.get("created"),
                "external_id": str(item.get("id") or ""),
                "raw": item,
            })
        return out

    async def close(self) -> None:
        return None


def _format_salary(lo, hi) -> str | None:
    if not lo and not hi:
        return None
    if lo and hi:
        return f"{int(lo)}-{int(hi)} EUR/an"
    return f"{int(lo or hi)} EUR/an"
