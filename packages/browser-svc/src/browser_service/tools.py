"""Outils haut niveau exposes aux agents. Chacun est independant du navigateur."""
from __future__ import annotations
from browser_service.service import browser_service


class SearchJobTool:
    """Outil de recherche d''offres. Utilise par Agent LinkedIn / Indeed / HelloWork."""

    def __init__(self, platform: str):
        self.platform = platform

    async def search(self, user_id: str, criteria: dict) -> list[dict]:
        async with browser_service.session(user_id, self.platform) as sess:
            html = await sess.navigate(self._build_url(criteria))
            return await self._parse(html, criteria)

    def _build_url(self, criteria: dict) -> str:
        if self.platform == "linkedin":
            q = criteria.get("keywords", "").replace(" ", "%20")
            return f"https://www.linkedin.com/jobs/search/?keywords={q}"
        if self.platform == "indeed":
            q = criteria.get("keywords", "").replace(" ", "+")
            return f"https://www.indeed.com/jobs?q={q}"
        if self.platform == "hellowork":
            q = criteria.get("keywords", "").replace(" ", "+")
            return f"https://www.hellowork.com/emplois?k={q}"
        return ""

    async def _parse(self, html: str, criteria: dict) -> list[dict]:
        """Extraction des offres depuis le HTML.

        V1 (dev/demo) : on retourne un echantillon deterministe a partir des criteres.
            Si le HTML est exploitable en prod, on branchera un parser par plateforme.
        V2 (prod) : extraction via LLM (browser_service.scrape_with_llm) ou un parser par plateforme.
        """
        keywords = criteria.get("keywords", "")
        max_n = min(int(criteria.get("max_results", 10)), 50)
        return [
            {
                "id": f"{self.platform}_{i}",
                "title": f"{keywords or 'Data'} - poste #{i+1}",
                "company": ["ACME", "DataCorp", "InnovTech", "Cloudly"][i % 4],
                "location": criteria.get("location", "France"),
                "contract": "alternance",
                "url": f"https://jobs.invalid/{self.platform}/{i}",
                "posted_at": "2026-07-0" + str((i % 5) + 1),
                "description": f"Offre recuperee via browser_service ({self.platform}).",
                "source": self.platform,
                "score": round(1 - i * 0.05, 3),
            }
            for i in range(max_n)
        ]


class FindContactTool:
    """Outil de recuperation de contact RH (utilise par Agent Emploi / Agent LinkedIn)."""

    async def find_hr_email(self, company: str, domain: str | None = None) -> dict | None:
        # Brancher Hunter.io ou Apollo (via connector manager)
        return None


class DownloadFileTool:
    """Telechargement de CV PDF (utilise par Agent CV)."""

    async def fetch(self, url: str) -> bytes:
        return b""