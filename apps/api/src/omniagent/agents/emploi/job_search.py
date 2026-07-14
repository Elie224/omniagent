"""Recherche d offres (LinkedIn, Indeed, HelloWork).

Deux backends :
- `MockBackend` (defaut) : genere des offres fictives deterministes (utile pour les tests, la demo, le mode hors-ligne).
- `BrowserBackend` : Playwright + stealth. Importe paresseusement pour eviter de casser les tests qui n ont pas Playwright.

Le backend est choisi a l instanciation. Si `playwright` n est pas disponible, `BrowserBackend`
leve une erreur explicite avec un message d installation.
"""
from __future__ import annotations
import asyncio
import hashlib
import math
import random
import unicodedata
import time
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, asdict
from typing import Protocol

from omniagent.connectors.manager import connector_manager
from omniagent.core.resilience.circuit_breaker import CircuitOpenError
from omniagent.core.config import settings


@dataclass
class JobOffer:
    id: str
    title: str
    company: str
    location: str
    contract: str
    url: str
    posted_at: str
    description: str
    source: str
    score: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class SearchBackend(Protocol):
    name: str
    async def search(self, criteria: dict) -> list[JobOffer]: ...


class MockBackend:
    """Genere des offres deterministes a partir des criteres (seed = hash(criteria))."""

    def __init__(self, source: str, titles: list[str] | None = None,
                 companies: list[str] | None = None, locations: list[str] | None = None):
        self.name = source
        self._titles = titles or ["Data Scientist", "ML Engineer", "Data Analyst",
                                    "BI Developer", "Data Engineer", "Analytics Engineer"]
        self._companies = companies or ["ACME", "DataCorp", "InnovTech", "Cloudly", "InsightLab"]
        self._locations = locations or ["Paris", "Lyon", "Bordeaux", "Lille", "Toulouse", "Remote"]

    def _seed(self, criteria: dict) -> random.Random:
        h = hashlib.sha256(repr(sorted(criteria.items())).encode()).hexdigest()
        return random.Random(int(h, 16))

    async def search(self, criteria: dict) -> list[JobOffer]:
        seed = self._seed(criteria)
        keywords = criteria.get("keywords", "")
        max_n = min(int(criteria.get("max_results", 20)), 50)
        results: list[JobOffer] = []
        for i in range(max_n):
            results.append(JobOffer(
                id=f"{self.name}_{i}_{abs(hash(keywords)) % 100000}",
                title=seed.choice(self._titles),
                company=seed.choice(self._companies),
                location=seed.choice(self._locations),
                contract=seed.choice(["alternance", "stage", "emploi"]),
                url=f"https://jobs.invalid/{self.name}/{i}",
                posted_at="2026-07-0" + str((i % 5) + 1),
                description=f"Offre {keywords} chez {self._companies[0]} (mock).",
                source=self.name,
                score=round(seed.random(), 3),
            ))
        # Tri par score desc
        results.sort(key=lambda o: -o.score)
        return results


class ConnectorBackend:
    """Backend qui делегуе a un connecteur plateforme (Adzuna, France Travail, WTTJ, etc).

    Le connecteur doit exposer `async def search(query, location, contract, max_results)`.
    """

    def __init__(self, source: str):
        self.name = source
        self._connector = connector_manager.get(source)

    _cache: dict[str, tuple[float, list[JobOffer]]] = {}

    @staticmethod
    def _parse_offer_datetime(value: str) -> datetime | None:
        if not value:
            return None
        txt = str(value).strip()
        if not txt:
            return None
        if txt.endswith("Z"):
            txt = txt[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(txt)
        except ValueError:
            try:
                dt = datetime.fromisoformat(txt.split("T")[0])
            except Exception:
                return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def _filter_by_recency(raw_offers: list[dict], recency_hours: int) -> list[dict]:
        if recency_hours <= 0:
            return raw_offers
        cutoff = datetime.now(timezone.utc) - timedelta(hours=recency_hours)
        out: list[dict] = []
        for offer in raw_offers:
            posted = ConnectorBackend._parse_offer_datetime(str(offer.get("posted_at") or ""))
            if posted is None:
                continue
            if posted >= cutoff:
                out.append(offer)
        return out

    @staticmethod
    def _norm_text(value: str) -> str:
        base = unicodedata.normalize("NFKD", value or "")
        no_accents = "".join(ch for ch in base if not unicodedata.combining(ch))
        return " ".join(no_accents.lower().split())

    @staticmethod
    def _filter_by_location(raw_offers: list[dict], location: str, radius: str) -> list[dict]:
        if not location:
            return raw_offers
        if (radius or "").lower() != "city":
            return raw_offers
        target = ConnectorBackend._norm_text(location)
        if not target:
            return raw_offers
        out: list[dict] = []
        for offer in raw_offers:
            loc = ConnectorBackend._norm_text(str(offer.get("location") or ""))
            if target in loc:
                out.append(offer)
        return out

    async def search(self, criteria: dict) -> list[JobOffer]:
        if self._connector is None:
            return []
        if not getattr(self._connector, "is_configured", True):
            # Connecteur non configure -> pas de resultats (et pas de bruit).
            return []
        cache_key = f"{self.name}:{repr(sorted(criteria.items()))}"
        ttl = max(0, int(getattr(settings, "employment_connector_cache_ttl_s", 300) or 300))
        if ttl > 0:
            cached = self._cache.get(cache_key)
            now = time.time()
            if cached and (now - cached[0] <= ttl):
                return [JobOffer(**o.to_dict()) for o in cached[1]]
        recency_hours = int(criteria.get("recency_hours") or 0)
        radius = str(criteria.get("radius") or "city")
        search_kwargs = {
            "query": criteria.get("keywords", ""),
            "location": criteria.get("location", ""),
            "contract": criteria.get("contract") if criteria.get("contract") not in (None, "all") else None,
            "max_results": int(criteria.get("max_results", 20)),
        }
        if self.name == "france_travail":
            radius_km = {"20km": 20, "50km": 50}.get(radius.lower())
            if radius_km:
                search_kwargs["diameter_km"] = radius_km
        if recency_hours > 0:
            if self.name == "adzuna":
                search_kwargs["max_days_old"] = max(1, math.ceil(recency_hours / 24))
            elif self.name == "france_travail":
                search_kwargs["min_creation_date"] = (
                    datetime.now(timezone.utc) - timedelta(hours=recency_hours)
                ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        async def _call_with_backoff(kwargs: dict) -> list[dict]:
            retries = max(0, int(getattr(settings, "employment_connector_max_retries", 2) or 2))
            base_sleep = float(getattr(settings, "employment_connector_backoff_base_s", 0.5) or 0.5)
            for attempt in range(retries + 1):
                try:
                    return await self._connector.search(**kwargs)
                except Exception as e:
                    msg = str(e).lower()
                    transient = any(t in msg for t in ["429", "rate", "too many", "timeout", "tempor", "503", "502", "connection"]) 
                    if attempt >= retries or not transient:
                        raise
                    await asyncio.sleep(base_sleep * (2 ** attempt))

        try:
            raw = await _call_with_backoff(search_kwargs)
        except TypeError:
            # Fallback: connecteur ne supporte pas encore les kwargs avances.
            search_kwargs.pop("max_days_old", None)
            search_kwargs.pop("min_creation_date", None)
            search_kwargs.pop("diameter_km", None)
            raw = await _call_with_backoff(search_kwargs)
        raw = self._filter_by_recency(raw, recency_hours)
        raw = self._filter_by_location(raw, str(criteria.get("location") or ""), radius)
        out: list[JobOffer] = []
        for r in raw:
            out.append(JobOffer(
                id=r.get("external_id") or r.get("id") or f"{self.name}_{len(out)}",
                title=r.get("title") or "",
                company=r.get("company") or "",
                location=r.get("location") or "",
                contract=r.get("contract") or "",
                url=r.get("url") or "",
                posted_at=str(r.get("posted_at") or ""),
                description=r.get("description") or "",
                source=self.name,
                score=float(r.get("score", 0.0)) if isinstance(r.get("score"), (int, float)) else 0.0,
            ))
        if ttl > 0:
            self._cache[cache_key] = (time.time(), [JobOffer(**o.to_dict()) for o in out])
        return out


class BrowserBackend:
    """Backend Playwright + stealth. Import paresseux."""

    def __init__(self, source: str, base_url: str):
        self.name = source
        self._base = base_url

    async def search(self, criteria: dict) -> list[JobOffer]:
        try:
            from playwright.async_api import async_playwright
            from playwright_stealth import stealth_async
        except ImportError as e:
            raise RuntimeError(
                f"Backend browser indisponible pour {self.name}. "
                "Installer playwright + playwright-stealth et executer `playwright install chromium`."
            ) from e
        keywords = criteria.get("keywords", "")
        location = criteria.get("location", "France")
        results: list[JobOffer] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await stealth_async(page)
                url = f"{self._base}?q={keywords}&l={location}"
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                # Extraction DOM basique (selector a adapter par plateforme).
                # On ne pretend pas etre exhaustif : on capture titre/entreprise si presents.
                items = await page.query_selector_all("a[href*=/job/], a[href*=/offre/]")
                for i, item in enumerate(items[:50]):
                    title = (await item.inner_text())[:120]
                    results.append(JobOffer(
                        id=f"{self.name}_{i}",
                        title=title.strip() or f"Offre {keywords}",
                        company="(a extraire)",
                        location=location,
                        contract="(a extraire)",
                        url=await item.get_attribute("href") or "",
                        posted_at="",
                        description="",
                        source=self.name,
                    ))
            finally:
                await browser.close()
        return results




class MultiSourceBackend:
    """Backend avec fallback sequentiel entre plusieurs sources.

    Comportement :
      - On essaie les sources dans l ordre donne
      - Si une source leve une exception, on passe a la suivante
      - Des qu une source retourne au moins une offre, on s arrete
      - Si toutes echouent ou retournent vide, on tente quand meme les suivantes
        (au cas ou une source renvoie [] sans echouer : on combine)

    But : resilience aux plateformes instables. Si LinkedIn crashe, Indeed prend
    le relais. On ne lance pas N appels en parallele, donc on respecte les rate
    limits d autant mieux.
    """

    def __init__(self, sources: list, name: str = "multi", use_breaker: bool = False):
        # sources : list[SearchBackend] dans l ordre de priorite
        self._sources = sources
        self.name = name
        self._last_errors: dict[str, str] = {}
        self._use_breaker = use_breaker

    @property
    def last_errors(self) -> dict[str, str]:
        """Detail des erreurs rencontrees sur la derniere recherche (par source)."""
        return dict(self._last_errors)

    async def search(self, criteria: dict) -> list[JobOffer]:
        self._last_errors = {}
        aggregated: list[JobOffer] = []
        for backend in self._sources:
            try:
                if self._use_breaker:
                    # On passe par le circuit breaker par nom de source, sans
                    # toucher au connector_registry (qui exige un ConnectorSpec).
                    # C est exactement le meme breaker que connector_manager.call()
                    # utiliserait, juste sans la couche get()/use().
                    breaker = connector_manager.breaker(backend.name)
                    offers = await breaker.call(backend.search, criteria)
                else:
                    offers = await backend.search(criteria)
            except CircuitOpenError as e:
                # Breaker ouvert pour cette source : on note et on bascule.
                self._last_errors[backend.name] = f"circuit_open: {e}"
                continue
            except Exception as e:
                self._last_errors[backend.name] = f"{type(e).__name__}: {e}"
                # On continue avec la source suivante
                continue
            if offers:
                # Premiere source qui retourne des resultats : on prend et on s arrete
                return offers
            # Liste vide : on tente la suivante mais on garde la trace
            self._last_errors[backend.name] = "empty_result"
        # Aucune source n a donne de resultat : on renvoie l agregat (probablement vide)
        return aggregated

class JobSearcher:
    """Coordonne la recherche d offres sur les 3 plateformes via le backend choisi."""

    def __init__(self, browser, user_profile: dict, backend: str = "mock"):
        self.profile = user_profile
        # En mode fallback on delaisse le parallel-gather (voir search())
        self._fallback_mode = (backend == "fallback")
        if backend == "mock":
            self._backends: list[SearchBackend] = [
                MockBackend("linkedin"),
                MockBackend("indeed"),
                MockBackend("hellowork"),
            ]
        elif backend == "browser":
            self._backends = [
                BrowserBackend("linkedin", "https://www.linkedin.com/jobs/search"),
                BrowserBackend("indeed", "https://fr.indeed.com/jobs"),
                BrowserBackend("hellowork", "https://www.hellowork.com/search"),
            ]
        elif backend == "fallback":
            # Fallback sequentiel : on essaie linkedin d abord, puis indeed, puis hellowork.
            # Si la 1ere source crashe ou retourne vide, on passe a la suivante.
            # use_breaker=True : chaque source est protegee par son propre circuit
            # breaker. Apres 5 echecs consecutifs, la source est skippee instantanement.
            self._backends = [
                MultiSourceBackend([
                    MockBackend("linkedin"),
                    MockBackend("indeed"),
                    MockBackend("hellowork"),
                ], name="fallback", use_breaker=True),
            ]

        else:
            raise ValueError(f"backend inconnu: {backend}")

    async def search(self, criteria: dict) -> list[JobOffer]:
        # Mode fallback : on delaisse le parallel-gather (qui ne sait pas faire
        # de sequentiel inter-sources) et on laisse MultiSourceBackend orchestrer.
        if self._fallback_mode:
            return await self._backends[0].search(criteria)
        tasks = []
        if criteria.get("include_linkedin", True):
            tasks.append(self._run("linkedin", criteria))
        if criteria.get("include_indeed", True):
            tasks.append(self._run("indeed", criteria))
        if criteria.get("include_hellowork", True):
            tasks.append(self._run("hellowork", criteria))
        results_nested = await asyncio.gather(*tasks, return_exceptions=True)
        out: list[JobOffer] = []
        for r in results_nested:
            if isinstance(r, Exception):
                # On log et on continue
                print(f"[JobSearcher] backend error: {r}")
                continue
            out.extend(r)
        out.sort(key=lambda o: -o.score)
        return out

    async def _run(self, source: str, criteria: dict) -> list[JobOffer]:
        for b in self._backends:
            if b.name == source:
                return await b.search(criteria)
        return []
