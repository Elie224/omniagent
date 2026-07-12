"""Trouve le contact RH d une entreprise (Hunter.io en priorite)."""
from __future__ import annotations
from typing import Optional

from omniagent.connectors.plateformes.hunter import HunterConnector


class ContactFinder:
    def __init__(self, hunter_api_key: str = ""):
        self._hunter = HunterConnector(hunter_api_key)

    async def find_hr_email(self, company: str,
                              company_domain: str | None = None) -> dict | None:
        """Retourne {name, email, position, source} ou None.

        Necessite `HUNTER_API_KEY`. Sans cle, leve une RuntimeError explicite.
        """
        result = await self._hunter.find_email(company, company_domain)
        if result is None:
            return None
        return {
            "name": result.get("name"),
            "email": result.get("email"),
            "role": result.get("position"),
            "source": result.get("source"),
        }

    async def health(self) -> bool:
        return await self._hunter.health_check()
