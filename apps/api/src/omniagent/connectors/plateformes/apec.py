"""APEC connector (Association Pour l Emploi des Cadres).

API officielle : https://api.apec.fr (recrutement/apec/api-offres)
Auth : OAuth2 (client_credentials). Inscription sur https://www.apec.fr/recruteur/mes-services.html
pour obtenir un compte recruteur avec acces API.

Variables d env :
  APEC_CLIENT_ID     : client ID OAuth2
  APEC_CLIENT_SECRET : client secret OAuth2
  APEC_SCOPE         : defaut 'api_offres'

Quand les cles manquent, on bascule sur un mock (offres cadres FR representatives).
"""
from __future__ import annotations
import os
import time
import logging
from typing import Any

import httpx

from omniagent.connectors.base.connector import Connector


logger = logging.getLogger(__name__)

_TOKEN_URL = "https://api.apec.fr/oauth2/v1/token"
_SEARCH_URL = "https://api.apec.fr/api-offres/v1/offres/search"


class APECConnector(Connector):
    name = "apec"
    category = "plateformes"

    def __init__(self, client_id: str = "", client_secret: str = "",
                 scope: str = "api_offres", timeout: float = 15.0):
        self._client_id = client_id or os.getenv("APEC_CLIENT_ID", "")
        self._client_secret = client_secret or os.getenv("APEC_CLIENT_SECRET", "")
        self._scope = scope or os.getenv("APEC_SCOPE", "api_offres")
        self._timeout = timeout
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    @property
    def is_configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    async def _get_token(self) -> str | None:
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.post(
                    _TOKEN_URL,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "scope": self._scope,
                    },
                )
                if r.status_code != 200:
                    logger.warning("APEC token HTTP %s", r.status_code)
                    return None
                data = r.json()
                self._token = data.get("access_token")
                self._token_expires_at = time.time() + float(data.get("expires_in", 3600))
                return self._token
        except Exception as e:
            logger.warning("APEC token fetch failed: %s", e)
            return None

    async def health_check(self) -> bool:
        return self.is_configured

    async def search(self, query: str, location: str = "",
                       contract: str | None = None,
                       max_results: int = 30) -> list[dict]:
        if not self.is_configured:
            return _mock_apec(query, location, contract, max_results)
        token = await self._get_token()
        if not token:
            return _mock_apec(query, location, contract, max_results)
        params: dict[str, Any] = {
            "motsCles": query,
            "range": f"0-{min(max_results - 1, 99)}",
        }
        if location:
            params["lieux"] = location
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.get(_SEARCH_URL,
                                 params=params,
                                 headers={"Authorization": f"Bearer {token}"})
                if r.status_code != 200:
                    logger.warning("APEC search HTTP %s", r.status_code)
                    return _mock_apec(query, location, contract, max_results)
                data = r.json()
        except Exception as e:
            logger.warning("APEC search failed: %s", e)
            return _mock_apec(query, location, contract, max_results)

        out: list[dict] = []
        for item in (data.get("resultats") or data.get("offres") or []):
            out.append({
                "title": item.get("intitule") or item.get("title") or "",
                "company": item.get("nomCommercial") or item.get("entreprise") or "",
                "location": item.get("lieu") or item.get("localisation") or "",
                "url": item.get("urlOffre") or item.get("url") or "",
                "source": "apec",
                "description": (item.get("description") or "")[:600],
                "contract": (item.get("typeContrat") or contract or "").lower() or None,
                "posted_at": item.get("datePublication") or item.get("dateCreation"),
                "external_id": str(item.get("id") or item.get("numeroOffre") or ""),
                "raw": item,
            })
        return out

    async def close(self) -> None:
        return None


def _mock_apec(query: str, location: str, contract: str | None,
                 max_results: int) -> list[dict]:
    """Mock APEC : offres cadres representatives (grandes entreprises FR)."""
    base = [
        {"title": "Data Scientist Senior", "company": "EDF", "location": "Paris",
         "contract": "cdi", "id": "APEC-MOCK-001"},
        {"title": "Lead Machine Learning Engineer", "company": "AXA", "location": "Paris",
         "contract": "cdi", "id": "APEC-MOCK-002"},
        {"title": "Data Engineer (Python/Spark)", "company": "SNCF", "location": "Saint-Denis",
         "contract": "cdi", "id": "APEC-MOCK-003"},
        {"title": "Architecte Big Data", "company": "Credit Agricole", "location": "Montrouge",
         "contract": "cdi", "id": "APEC-MOCK-004"},
        {"title": "Senior Python Developer", "company": "Safran", "location": "Paris",
         "contract": "cdi", "id": "APEC-MOCK-005"},
        {"title": "Engineering Manager Data", "company": "Renault", "location": "Guyancourt",
         "contract": "cdi", "id": "APEC-MOCK-006"},
        {"title": "ML Ops Engineer", "company": "BNP Paribas", "location": "Paris",
         "contract": "cdi", "id": "APEC-MOCK-007"},
        {"title": "Data Analyst Confirmé", "company": "L Oreal", "location": "Clichy",
         "contract": "cdi", "id": "APEC-MOCK-008"},
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
            "url": f"https://www.apec.fr/candidat/recherche-emploi.html/offre/{o['id'].lower()}",
            "source": "apec",
            "description": f"Recherche : {query}. Entreprise : {o['company']} (cadre).",
            "contract": o["contract"],
            "posted_at": "2026-07-02",
            "external_id": o["id"],
            "raw": {"_mock": True, **o},
        })
        if len(out) >= max_results:
            break
    return out
