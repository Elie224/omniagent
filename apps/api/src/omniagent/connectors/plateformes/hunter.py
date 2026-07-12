"""Hunter.io : recherche emails pro."""
import httpx

from omniagent.connectors.base.connector import Connector


class HunterConnector(Connector):
    name = "hunter"
    category = "plateformes"
    BASE_URL = "https://api.hunter.io/v2"

    def __init__(self, api_key: str):
        self._api_key = api_key

    async def health_check(self) -> bool:
        return bool(self._api_key)

    async def find_email(self, company: str, domain: str | None = None) -> dict | None:
        params = {"company": company, "api_key": self._api_key}
        if domain:
            params["domain"] = domain
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self.BASE_URL}/email-finder", params=params)
            if r.status_code != 200:
                return None
            data = r.json().get("data", {}) or {}
            if not data.get("email"):
                return None
            return {"name": data.get("first_name"), "email": data["email"],
                    "position": data.get("position"), "source": self.name}

    async def close(self) -> None:
        return None