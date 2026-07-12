"""France Travail (ex Pole Emploi) connector.

API officielle : https://francetravail.io/data/api/offres-emploi
Auth : OAuth2 client_credentials (inscription sur francetravail.io).

Variables d env :
  FT_CLIENT_ID     : client ID OAuth2
  FT_CLIENT_SECRET : client secret OAuth2
  FT_SCOPE         : defaut 'api_offresdemploiv2'

Quand les cles manquent, on bascule sur un dataset mock pour dev/demo
(offres representatives issues du domaine public).
"""
from __future__ import annotations
import os
import time
import logging
from typing import Any

import httpx

from omniagent.connectors.base.connector import Connector


logger = logging.getLogger(__name__)

_TOKEN_URL = "https://francetravail.io/connexion/oauth2/access_token"
_API_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"


class FranceTravailConnector(Connector):
    name = "france_travail"
    category = "plateformes"

    def __init__(self, client_id: str = "", client_secret: str = "",
                 scope: str = "api_offresdemploiv2", timeout: float = 15.0):
        self._client_id = client_id or os.getenv("FT_CLIENT_ID", "")
        self._client_secret = client_secret or os.getenv("FT_CLIENT_SECRET", "")
        self._scope = scope or os.getenv("FT_SCOPE", "api_offresdemploiv2")
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
                    logger.warning("FT token HTTP %s", r.status_code)
                    return None
                data = r.json()
                self._token = data.get("access_token")
                self._token_expires_at = time.time() + float(data.get("expires_in", 1500))
                return self._token
        except Exception as e:
            logger.warning("FT token fetch failed: %s", e)
            return None

    async def health_check(self) -> bool:
        return self.is_configured

    async def search(self, query: str, location: str = "",
                       contract: str | None = None,
                       max_results: int = 30) -> list[dict]:
        if not self.is_configured:
            return _mock_offers(query, location, contract, max_results)
        token = await self._get_token()
        if not token:
            return _mock_offers(query, location, contract, max_results)
        params: dict[str, Any] = {
            "motsCles": query,
            "range": f"0-{min(max_results - 1, 149)}",
        }
        if location:
            params["lieu"] = location
        # FT supporte filtres par typeContrat (CDI, CDD, MIS, SAI, ALT, etc.)
        contract_map = {"cdi": "CDI", "cdd": "CDD", "stage": "SAI", "alternance": "ALT"}
        if contract and contract in contract_map:
            params["typeContrat"] = contract_map[contract]
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.get(_API_URL,
                                 params=params,
                                 headers={"Authorization": f"Bearer {token}"})
                if r.status_code != 200:
                    logger.warning("FT search HTTP %s", r.status_code)
                    return _mock_offers(query, location, contract, max_results)
                data = r.json()
        except Exception as e:
            logger.warning("FT search failed: %s", e)
            return _mock_offers(query, location, contract, max_results)

        out: list[dict] = []
        for item in (data.get("resultats") or []):
            out.append({
                "title": item.get("intitule") or "",
                "company": item.get("entreprise") or {},
                "company_name": (item.get("entreprise") or {}).get("nom") or "",
                "location": item.get("lieuTravail") or {},
                "location_label": (item.get("lieuTravail") or {}).get("libelle") or "",
                "url": f"https://candidat.francetravail.fr/offres/recherche/detail/{item.get('id')}",
                "source": "france_travail",
                "description": (item.get("description") or "")[:600],
                "contract": (item.get("typeContrat") or "").lower() or None,
                "posted_at": item.get("dateCreation"),
                "external_id": item.get("id") or "",
                "raw": item,
            })
        # Fix : on retourne company_name et location_label directement
        for o in out:
            o["company"] = o.pop("company_name", o["company"])
            o["location"] = o.pop("location_label", o["location"])
        return out

    async def close(self) -> None:
        return None


def _mock_offers(query: str, location: str, contract: str | None,
                  max_results: int) -> list[dict]:
    """Dataset mock pour dev sans cle FT. Offres representatives."""
    base = [
        {"title": "Data Scientist", "company": "Capgemini", "location": "Paris",
         "contract": "cdi", "posted_at": "2026-07-04", "id": "FT-MOCK-001"},
        {"title": "ML Engineer Senior", "company": "OVHcloud", "location": "Roubaix",
         "contract": "cdi", "posted_at": "2026-07-03", "id": "FT-MOCK-002"},
        {"title": "Data Engineer", "company": "Banque de France", "location": "Paris",
         "contract": "cdi", "posted_at": "2026-07-02", "id": "FT-MOCK-003"},
        {"title": "Alternance Data Scientist", "company": "BNP Paribas", "location": "Paris",
         "contract": "alternance", "posted_at": "2026-07-01", "id": "FT-MOCK-004"},
        {"title": "Stage Data Analyst", "company": "Carrefour", "location": "Massy",
         "contract": "stage", "posted_at": "2026-07-01", "id": "FT-MOCK-005"},
        {"title": "MLOps Engineer", "company": "Doctolib", "location": "Levallois-Perret",
         "contract": "cdi", "posted_at": "2026-06-30", "id": "FT-MOCK-006"},
        {"title": "Senior Python Developer", "company": "Société Générale", "location": "La Defense",
         "contract": "cdi", "posted_at": "2026-06-30", "id": "FT-MOCK-007"},
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
            "url": f"https://candidat.francetravail.fr/offres/recherche/detail/{o['id']}",
            "source": "france_travail",
            "description": f"Recherche : {query}. Localisation : {o['location']}.",
            "contract": o["contract"],
            "posted_at": o["posted_at"],
            "external_id": o["id"],
            "raw": {"_mock": True, **o},
        })
        if len(out) >= max_results:
            break
    return out
