"""France Travail (ex Pole Emploi) connector.

API officielle : https://francetravail.io/data/api/offres-emploi
Auth : OAuth2 client_credentials (inscription sur francetravail.io).

Variables d env requises (mode reel) :
  FT_CLIENT_ID     : client ID OAuth2 (a creer sur https://francetravail.io)
  FT_CLIENT_SECRET : client secret OAuth2
  FT_SCOPE         : defaut 'api_offresdemploiv2'

Variables d env optionnelles :
  FT_BASE_URL      : defaut 'https://api.francetravail.io'
  FT_TOKEN_URL     : defaut 'https://francetravail.io/connexion/oauth2/access_token'
  FT_CACHE_TTL     : defaut 300 (secondes ; 0 = desactive)
  FT_TIMEOUT       : defaut 15 (secondes)

Quand les cles manquent, on bascule sur un dataset mock pour dev/demo
(offres representatives issues du domaine public).
"""
from __future__ import annotations
import os
import time
import logging
import hashlib
import json
import asyncio
from typing import Any

import httpx

from omniagent.connectors.base.connector import Connector
from omniagent.core.config import settings


logger = logging.getLogger(__name__)

_TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
_API_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
_REFERENCE_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/referentiel/"
_REQUIRED_SCOPES = ("api_offresdemploiv2", "o2dsoffre")

# Mapping des filtres FT v2 : https://francetravail.io/data/api/offres-emploi
CONTRACT_MAP = {
    "cdi": "CDI", "cdd": "CDD", "interim": "MIS", "mission": "MIS",
    "saisonnier": "SAI", "stage": "SAI", "alternance": "ALT", "apprentissage": "ALT",
    "liberal": "LIB", "freelance": "LIB",
}
EXPERIENCE_MAP = {
    "junior": "0", "0-1": "0", "<1": "0",
    "1-3": "1", "confirme": "1",
    "3-5": "2", "senior": "2",
    ">5": "3", "expert": "3",
}
QUALIFICATION_MAP = {
    "sans_diplome": "0",
    "cap_bep": "1", "bac": "2",
    "bac2": "3", "bac3": "4", "bac4": "4",
    "bac5": "5", "master": "5",
    "bac6": "6", "doctorat": "7",
}# Code source de la classe FranceTravailConnector (a concatener a france_travail.py)

class FranceTravailConnector(Connector):
    """Connecteur France Travail (API Offres Emploi v2).

    Fonctionnalites :
      - OAuth2 client_credentials avec cache du token (TTL = expires_in - 60s).
      - Recherche d offres avec filtres : mots-cles, lieu (code INSEE ou commune),
        typeContrat, experience, qualification, diametre (rayon), minCreationDate (recence),
        salaire minimum, distance, domaine professionnel.
      - Pagination via range (start-end).
      - Cache memoire TTL des resultats (optionnel, defaut 300s).
      - Fallback automatique vers un dataset mock si creds absentes.

    Rate limits FT (par defaut, voir doc) :
      - 30 requetes/minute pour /search
      - Le cache aide enormement a rester sous la limite pour les memes criteres.
    """

    name = "france_travail"
    category = "plateformes"

    @staticmethod
    def _normalize_scope(scope: str) -> str:
        parts = [p for p in (scope or "").split() if p]
        for required in _REQUIRED_SCOPES:
            if required not in parts:
                parts.append(required)
        return " ".join(parts)

    def __init__(self, client_id: str = "", client_secret: str = "",
                 scope: str = "api_offresdemploiv2 o2dsoffre", timeout: float = 0):
        self._client_id = client_id or settings.ft_client_id or os.getenv("FT_CLIENT_ID", "")
        self._client_secret = client_secret or settings.ft_client_secret or os.getenv("FT_CLIENT_SECRET", "")
        raw_scope = scope or os.getenv("FT_SCOPE", "api_offresdemploiv2 o2dsoffre")
        self._scope = self._normalize_scope(raw_scope)
        self._timeout = timeout or float(os.getenv("FT_TIMEOUT", "15"))
        self._base_url = os.getenv("FT_BASE_URL", "https://api.francetravail.io").rstrip("/")
        self._token_url = os.getenv("FT_TOKEN_URL", _TOKEN_URL)
        try:
            self._cache_ttl = int(os.getenv("FT_CACHE_TTL", "300"))
        except ValueError:
            self._cache_ttl = 300
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        # Cache memoire : (cache_key -> (timestamp, offers))
        self._cache: dict[str, tuple[float, list[dict]]] = {}
        self._mode_logged: bool = False  # pour eviter spam logs

    @property
    def is_configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    @property
    def mode(self) -> str:
        """Mode operationnel : real (API FT) ou mock (dataset local)."""
        return "real" if self.is_configured else "mock"

    def _log_mode_once(self) -> None:
        """Log le mode au premier appel (pour observabilite)."""
        if self._mode_logged:
            return
        self._mode_logged = True
        if self.is_configured:
            logger.info("[FT] connecteur en mode REAL (API France Travail)")
        else:
            logger.warning(
                "[FT] connecteur en mode MOCK (FT_CLIENT_ID/FT_CLIENT_SECRET absents). "
                "Pour activer le reel, voir apps/api/.env.example"
            )

    async def _get_token(self) -> str | None:
        """Recupere (ou reutilise) un access_token OAuth2."""
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.post(
                    self._token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "scope": self._scope,
                    },
                )
                if r.status_code != 200:
                    logger.warning("FT token HTTP %s body=%s", r.status_code, r.text[:200])
                    return None
                data = r.json()
                self._token = data.get("access_token")
                if not self._token:
                    logger.warning("FT token KO: pas de access_token dans la reponse %s", data)
                    return None
                # expires_in par defaut 1500s (25 min) pour FT
                self._token_expires_at = time.time() + float(data.get("expires_in", 1500))
                logger.info("[FT] token OAuth OK, expire dans %ss", int(data.get("expires_in", 1500)))
                return self._token
        except httpx.ConnectError as e:
            # Firewall / antivirus / proxy bloque la sortie
            logger.warning(
                "FT token fetch: CONNEXION BLOQUEE (firewall/antivirus/proxy?). "
                "Erreur: %s. Verifiez que python.exe est autorise a sortir sur 443.",
                e,
            )
            return None
        except httpx.TimeoutException as e:
            logger.warning("FT token fetch: TIMEOUT apres %ss (%s)", self._timeout, e)
            return None
        except json.JSONDecodeError as e:
            # Le serveur a repondu mais avec du contenu non-JSON (souvent HTML : page d erreur FT)
            logger.warning(
                "FT token fetch: reponse non-JSON (probablement page HTML d erreur FT). "
                "Verifiez que le scope api_offresdemploiv2 est active sur francetravail.io. Erreur: %s",
                e,
            )
            return None
        except Exception as e:
            logger.warning("FT token fetch failed: %s", e)
            return None

    async def health_check(self) -> dict:
        """Health check : indique mode, token OK, latence approx."""
        info: dict[str, Any] = {
            "mode": self.mode,
            "configured": self.is_configured,
            "token_cached": self._token is not None,
            "cache_ttl_s": self._cache_ttl,
        }
        if self.is_configured:
            token = await self._get_token()
            info["token_ok"] = token is not None
            if token:
                info["token_expires_in_s"] = int(max(0, self._token_expires_at - time.time()))
        return info

    def _cache_key(self, params: dict) -> str:
        """Hash deterministe des parametres de recherche (pour cache)."""
        h = hashlib.sha256()
        for k in sorted(params.keys()):
            h.update(k.encode())
            h.update(b"=")
            h.update(repr(params[k]).encode())
            h.update(b"|")
        return h.hexdigest()

    def _get_cached(self, params: dict) -> list[dict] | None:
        if self._cache_ttl <= 0:
            return None
        k = self._cache_key(params)
        v = self._cache.get(k)
        if v is None:
            return None
        ts, offers = v
        if time.time() - ts > self._cache_ttl:
            return None
        return offers

    def _set_cached(self, params: dict, offers: list[dict]) -> None:
        if self._cache_ttl <= 0:
            return
        k = self._cache_key(params)
        self._cache[k] = (time.time(), offers)
    async def search(self, query: str, location: str = "",
                       contract: str | None = None,
                       max_results: int = 30,
                       # --- Filtres avances optionnels ---
                       diameter_km: int | None = None,
                       min_creation_date: str | None = None,  # ISO 8601 : "2026-07-01T00:00:00Z"
                       experience: str | None = None,        # "junior", "confirme", "senior", "expert"
                       qualification: str | None = None,     # "bac", "master", "doctorat", ...
                       min_salary: float | None = None,       # salaire annuel minimum en euros
                       domaine: str | None = None,            # code domaine FT (ex: "M1402", "M1805")
                       range_start: int = 0,
                       ) -> list[dict]:
        """Recherche d offres France Travail.

        Args:
            query: mots-cles (motsCles).
            location: commune ou code postal (libelle FT, ex: "Paris", "75001", "Lyon").
            contract: cdi / cdd / interim / alternance / stage / liberal.
            max_results: nb max d offres (defaut 30, max 150 via pagination).
            diameter_km: rayon en km autour de location (0..200). None = pas de filtre.
            min_creation_date: ISO 8601 pour filtrer les offres recentes.
            experience: niveau d experience souhaite.
            qualification: niveau de diplome souhaite.
            min_salary: salaire annuel minimum (filtre FT si supporte).
            domaine: code ROME ou code domaine FT.
            range_start: offset pour pagination (defaut 0).

        Returns:
            Liste d offres normalisees au format pipeline.
        """
        self._log_mode_once()

        # Construction des parametres FT
        params: dict[str, Any] = {
            "motsCles": query or "",
            "range": f"{range_start}-{range_start + min(max_results, 150) - 1}",
        }
        if location:
            params["lieu"] = location
        if contract:
            ct = CONTRACT_MAP.get(contract.lower())
            if ct:
                params["typeContrat"] = ct
            else:
                logger.debug("[FT] contrat inconnu : %s (ignore)", contract)
        if diameter_km is not None and diameter_km > 0:
            params["diameter"] = str(min(int(diameter_km), 200))
        if min_creation_date:
            params["minCreationDate"] = min_creation_date
        if experience:
            ex = EXPERIENCE_MAP.get(experience.lower())
            if ex:
                params["experience"] = ex
        if qualification:
            q = QUALIFICATION_MAP.get(qualification.lower())
            if q:
                params["qualification"] = q
        if min_salary is not None and min_salary > 0:
            params["salaireMin"] = str(int(min_salary))
        if domaine:
            params["domaine"] = domaine

        # Cache hit
        cached = self._get_cached(params)
        if cached is not None:
            logger.debug("[FT] cache hit (%d offres)", len(cached))
            return cached

        # Mode reel
        if self.is_configured:
            token = await self._get_token()
            if not token:
                logger.warning("[FT] token KO, fallback mock")
                offers = _mock_offers(query, location, contract, max_results)
            else:
                try:
                    async with httpx.AsyncClient(timeout=self._timeout) as c:
                        r = await c.get(
                            f"{self._base_url}/partenaire/offresdemploi/v2/offres/search",
                            params=params,
                            headers={"Authorization": f"Bearer {token}"},
                        )
                        if r.status_code not in (200, 206):
                            logger.warning("[FT] search HTTP %s body=%s",
                                            r.status_code, r.text[:200])
                            offers = _mock_offers(query, location, contract, max_results)
                        else:
                            data = r.json()
                            offers = _normalize_ft_response(data, self.name)
                except Exception as e:
                    logger.warning("[FT] search failed: %s", e)
                    offers = _mock_offers(query, location, contract, max_results)
        else:
            # Pas configure -> mock
            offers = _mock_offers(query, location, contract, max_results)

        self._set_cached(params, offers)
        return offers

    async def get_offer_details(self, offer_id: str) -> dict | None:
        """Recupere le detail d une offre par son ID FT.

        Endpoint : GET /partenaire/offresdemploi/v2/offres/{id}
        """
        if not self.is_configured:
            return None
        token = await self._get_token()
        if not token:
            return None
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.get(
                    f"{self._base_url}/partenaire/offresdemploi/v2/offres/{offer_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )
                if r.status_code != 200:
                    logger.warning("[FT] offer detail HTTP %s", r.status_code)
                    return None
                return r.json()
        except Exception as e:
            logger.warning("[FT] offer detail failed: %s", e)
            return None

    async def close(self) -> None:
        """Cleanup (cache + token)."""
        self._cache.clear()
        self._token = None
        return None

def _normalize_ft_response(data: dict, source_name: str) -> list[dict]:
    """Normalise la reponse FT v2 vers le schema Offer interne.

    Schema FT : https://francetravail.io/data/api/offres-emploi
    Champs cles :
      - id, intitule, description, dateCreation, dateActualisation
      - lieuTravail.libelle, lieuTravail.commune, lieuTravail.codePostal
      - entreprise.nom, entreprise.description, entreprise.logo
      - typeContrat, typeContratLibelle
      - salaire.libelle, salaire.min, salaire.max
      - experience.libelle, experience.exigenceCode
      - qualification.libelle, qualification.code
      - competences, qualitesProfessionnelles, langues
      - contact (coordonnees recruteur si disponibles)
      - agence (cabinet de recrutement si applicable)
    """
    out: list[dict] = []
    for item in (data.get("resultats") or []):
        lieu = item.get("lieuTravail") or {}
        ent = item.get("entreprise") or {}
        sal = item.get("salaire") or {}
        out.append({
            "title": item.get("intitule") or "",
            "company": ent.get("nom") or "Entreprise confidentielle",
            "location": lieu.get("libelle") or lieu.get("commune") or "",
            "location_city": lieu.get("commune") or "",
            "location_postal": lieu.get("codePostal") or "",
            "url": f"https://candidat.francetravail.fr/offres/recherche/detail/{item.get('id')}",
            "source": source_name,
            "description": (item.get("description") or "")[:600],
            "contract": item.get("typeContrat") or "",
            "contract_label": item.get("typeContratLibelle") or "",
            "posted_at": item.get("dateCreation"),
            "updated_at": item.get("dateActualisation"),
            "external_id": item.get("id") or "",
            "salary": _extract_salary(sal),
            "experience": (item.get("experience") or {}).get("libelle"),
            "qualification": (item.get("qualification") or {}).get("libelle"),
            "skills": [c.get("libelle") for c in (item.get("competences") or []) if c.get("libelle")],
            "languages": [l.get("libelle") for l in (item.get("langues") or []) if l.get("libelle")],
            "permit": [p.get("libelle") for p in (item.get("permis") or []) if p.get("libelle")],
            "contact": item.get("contact") or {},
            "agence": item.get("agence") or {},
            "raw": item,
        })
    return out


def _extract_salary(sal: dict) -> dict:
    """Extrait un dict salary normalise a partir du bloc salaire FT."""
    if not sal:
        return {}
    out: dict[str, Any] = {}
    libelle = sal.get("libelle")
    if libelle:
        out["label"] = libelle
    mn = sal.get("minimum")
    if isinstance(mn, (int, float)):
        out["min"] = float(mn)
    mx = sal.get("maximum")
    if isinstance(mx, (int, float)):
        out["max"] = float(mx)
    unit = sal.get("uniteDuree") or sal.get("periode")
    if unit:
        out["period"] = unit  # "Mensuel", "Annuel", "Horaire"
    return out


def _mock_offers(query: str, location: str, contract: str | None,
                  max_results: int) -> list[dict]:
    """Dataset mock pour dev sans cle FT. Offres representatives.

    Ce dataset couvre 5 plateformes simulees (france_travail, adzuna, wttj,
    linkedin, indeed, hellowork, themuse) pour permettre un dev/test complet
    sans aucune cle API. Les champs sont normalises comme la vraie API FT.
    """
    base = [
        {"title": "Data Scientist", "company": "Capgemini", "location": "Paris (75)",
         "contract": "CDI", "posted_at": "2026-07-04", "id": "FT-MOCK-001",
         "experience": "2 a 5 ans", "qualification": "Bac+5 et plus",
         "salary": {"label": "45-55k Euros/an"}},
        {"title": "ML Engineer Senior", "company": "OVHcloud", "location": "Roubaix (59)",
         "contract": "CDI", "posted_at": "2026-07-03", "id": "FT-MOCK-002",
         "experience": "5 ans et plus", "qualification": "Bac+5 et plus",
         "salary": {"label": "55-70k Euros/an"}},
        {"title": "Data Engineer", "company": "Banque de France", "location": "Paris (75)",
         "contract": "CDI", "posted_at": "2026-07-02", "id": "FT-MOCK-003",
         "experience": "1 a 3 ans", "qualification": "Bac+3, Bac+4",
         "salary": {"label": "40-50k Euros/an"}},
        {"title": "Alternance Data Scientist", "company": "BNP Paribas", "location": "Paris (75)",
         "contract": "Alternance", "posted_at": "2026-07-01", "id": "FT-MOCK-004",
         "experience": "Aucune experience", "qualification": "Bac+5 et plus",
         "salary": {"label": "Selon grille alternance"}},
        {"title": "Stage Data Analyst", "company": "Carrefour", "location": "Massy (91)",
         "contract": "Stage", "posted_at": "2026-07-01", "id": "FT-MOCK-005",
         "experience": "Aucune experience", "qualification": "Bac+3, Bac+4"},
        {"title": "MLOps Engineer", "company": "Doctolib", "location": "Levallois-Perret (92)",
         "contract": "CDI", "posted_at": "2026-06-30", "id": "FT-MOCK-006",
         "experience": "3 a 5 ans", "qualification": "Bac+5 et plus",
         "salary": {"label": "50-60k Euros/an"}},
        {"title": "Senior Python Developer", "company": "Societe Generale", "location": "La Defense (92)",
         "contract": "CDI", "posted_at": "2026-06-30", "id": "FT-MOCK-007",
         "experience": "5 ans et plus", "qualification": "Bac+5 et plus",
         "salary": {"label": "55-65k Euros/an"}},
        {"title": "Lead Data Engineer", "company": "Cdiscount", "location": "Bordeaux (33)",
         "contract": "CDI", "posted_at": "2026-06-29", "id": "FT-MOCK-008",
         "experience": "5 ans et plus", "qualification": "Bac+5 et plus",
         "salary": {"label": "60-75k Euros/an"}},
    ]
    out = []
    q = (query or "").lower()
    for o in base:
        if q and q not in o["title"].lower() and q not in o["company"].lower():
            continue
        if contract and o["contract"].lower() != contract.lower():
            # mapping inverse : on accepte les alias
            mapped = {"cdi": "cdi", "cdd": "cdd", "alternance": "alternance",
                      "stage": "stage", "interim": "interim", "mission": "interim"}
            want = mapped.get(contract.lower())
            if want and o["contract"].lower() != want:
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
            "contract_label": o["contract"],
            "posted_at": o["posted_at"],
            "experience": o.get("experience"),
            "qualification": o.get("qualification"),
            "salary": o.get("salary", {}),
            "external_id": o["id"],
            "raw": {"_mock": True, **o},
        })
        if len(out) >= max_results:
            break
    return out