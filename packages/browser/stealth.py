"""Navigateur Playwright avec anti-detection."""
from dataclasses import dataclass


@dataclass
class StealthConfig:
    proxy_url: str | None = None
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    locale: str = "fr-FR"
    timezone: str = "Europe/Paris"
    headless: bool = True


class StealthBrowser:
    """Wrapper Playwright avec fingerprint realiste."""

    def __init__(self, config: StealthConfig | None = None):
        self.config = config or StealthConfig()
        self._browser = None

    async def launch(self):
        from playwright.async_api import async_playwright
        pw = await async_playwright().start()
        launch_kwargs = {
            "headless": self.config.headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        }
        if self.config.proxy_url:
            launch_kwargs["proxy"] = {"server": self.config.proxy_url}
        self._browser = await pw.chromium.launch(**launch_kwargs)
        return self._browser

    async def new_context(self, storage_state: dict | None = None):
        if not self._browser:
            await self.launch()
        return await self._browser.new_context(
            user_agent=self.config.user_agent,
            locale=self.config.locale,
            timezone_id=self.config.timezone,
            storage_state=storage_state,
            viewport={"width": 1440, "height": 900},
        )

    async def close(self):
        if self._browser:
            await self._browser.close()
            self._browser = None