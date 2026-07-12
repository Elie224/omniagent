"""Service navigateur unique. Les agents ne parlent qu''a lui, jamais a Playwright directement."""
from __future__ import annotations
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Callable, Any


@dataclass
class BrowserConfig:
    headless: bool = True
    proxy_url: str | None = None
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    locale: str = "fr-FR"
    timezone: str = "Europe/Paris"


class BrowserService:
    """Point d''entree unique pour toutes les operations navigateur.

    Avantages :
    - les agents restent agnostiques de la techno (Playwright / Selenium / futur ...)
    - un seul endroit pour gerer anti-detection, sessions persistantes, proxies
    - facilite les tests (on peut mocker ce service)
    """

    def __init__(self, config: BrowserConfig | None = None):
        self.config = config or BrowserConfig()
        self._backend: str | None = None  # "playwright" par defaut
        self._session_store: dict[str, dict] = {}

    def use_backend(self, backend: str) -> None:
        """Permet de basculer vers Selenium / autre sans modifier les agents."""
        if backend not in {"playwright", "selenium", "undetected-chromedriver"}:
            raise ValueError(f"Backend inconnu: {backend}")
        self._backend = backend

    @asynccontextmanager
    async def session(self, user_id: str, platform: str) -> AsyncIterator["BrowserSession"]:
        sess = BrowserSession(self, user_id, platform, state=await self._load_session(user_id, platform))
        try:
            yield sess
        finally:
            await self._save_session(user_id, platform, sess.export_state())

    async def _load_session(self, user_id: str, platform: str) -> dict:
        return self._session_store.get(f"{user_id}_{platform}", {})

    async def _save_session(self, user_id: str, platform: str, state: dict) -> None:
        self._session_store[f"{user_id}_{platform}"] = state


@dataclass
class BrowserSession:
    service: BrowserService
    user_id: str
    platform: str
    state: dict

    async def navigate(self, url: str) -> str:
        """Retourne le HTML de la page."""
        if self.service._backend != "playwright":
            raise RuntimeError("Backend non implemente")
        # En prod : demarre Playwright, applique stealth, charge storage_state
        return ""

    async def click(self, selector: str) -> None:
        pass

    async def type(self, selector: str, text: str) -> None:
        pass

    async def extract(self, schema: dict, source_url: str) -> dict:
        """Extraction structuree via LLM sur le HTML (DOM parsing intelligent)."""
        html = await self.navigate(source_url)
        return {"html": html, "schema": schema}

    def export_state(self) -> dict:
        return {"cookies": [], "localStorage": {}, "user_id": self.user_id, "platform": self.platform}


# Singleton global
browser_service = BrowserService()
