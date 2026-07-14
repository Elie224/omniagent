"""Agent France Travail : utilise le connecteur plateforme france_travail."""
import logging
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any

from omniagent.connectors.manager import connector_manager


logger = logging.getLogger(__name__)


def _parse_offer_datetime(value: Any) -> datetime | None:
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


def _filter_by_recency(offers: list[dict], recency_hours: int) -> list[dict]:
    if recency_hours <= 0:
        return offers
    cutoff = datetime.now(timezone.utc) - timedelta(hours=recency_hours)
    out: list[dict] = []
    for offer in offers:
        posted = _parse_offer_datetime(offer.get("posted_at"))
        if posted is None:
            continue
        if posted >= cutoff:
            out.append(offer)
    return out


def _norm_text(value: str) -> str:
    base = unicodedata.normalize("NFKD", value or "")
    no_accents = "".join(ch for ch in base if not unicodedata.combining(ch))
    return " ".join(no_accents.lower().split())


def _filter_by_location(offers: list[dict], location: str, radius: str) -> list[dict]:
    if not location:
        return offers
    if (radius or "").lower() != "city":
        return offers
    target = _norm_text(location)
    if not target:
        return offers
    out: list[dict] = []
    for offer in offers:
        loc = _norm_text(str(offer.get("location") or ""))
        if target in loc:
            out.append(offer)
    return out


def _resolve_criteria(input_data: dict) -> dict:
    """Le runner passe `{"step": input_template, "context": ctx}`.
    On essaie de recuperer les criteres depuis :
      1. step.criteria (template du plan)
      2. context (dict injecte par l orchestrateur / main.py)
    Renvoie un dict avec keywords/location/contract/max_results si trouvable.
    """
    out: dict[str, Any] = {}
    step = input_data.get("step") or {}
    if isinstance(step, dict):
        c = step.get("criteria") or {}
        if isinstance(c, dict) and c:
            out.update(c)
    ctx = input_data.get("context") or {}
    if isinstance(ctx, dict):
        for key in ("keywords", "query", "location", "contract", "max_results", "recency_hours", "radius"):
            if key in ctx and ctx[key] not in (None, ""):
                out.setdefault(key, ctx[key])
    return out


async def run(input_data: dict, user_id: str) -> dict:
    """Recherche d offres sur france_travail via le connecteur dedie."""
    ctx = input_data.get("context") or {}
    requested_sources = set(ctx.get("sources") or [])
    if requested_sources and "france_travail" not in requested_sources:
        return {
            "agent": "agent_france_travail",
            "platform": "france_travail",
            "offers": [],
            "status": "skipped_source",
        }
    criteria = _resolve_criteria(input_data)
    if not criteria or not criteria.get("keywords") and not criteria.get("query"):
        return {"agent": "agent_france_travail", "platform": "france_travail",
                "offers": [], "status": "no_criteria"}
    connector = connector_manager.get("france_travail")
    if connector is None:
        logger.warning("france_travail connector not registered")
        return {"agent": "agent_france_travail", "platform": "france_travail",
                "offers": [], "status": "connector_unavailable"}
    query = criteria.get("keywords") or criteria.get("query") or ""
    location = criteria.get("location") or ""
    contract = criteria.get("contract") if criteria.get("contract") not in (None, "all") else None
    max_results = int(criteria.get("max_results") or 20)
    recency_hours = int(criteria.get("recency_hours") or 0)
    radius = str(criteria.get("radius") or "city")
    min_creation_date = None
    if recency_hours > 0:
        min_creation_date = (
            datetime.now(timezone.utc) - timedelta(hours=recency_hours)
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    try:
        offers = await connector.search(
            query=query, location=location,
            contract=contract,
            max_results=max_results,
            min_creation_date=min_creation_date,
        )
        offers = _filter_by_recency(offers, recency_hours)
        offers = _filter_by_location(offers, location, radius)
    except Exception as e:
        logger.warning("france_travail search failed: %s", e)
        return {"agent": "agent_france_travail", "platform": "france_travail",
                "offers": [], "status": "error", "error": str(e)}
    return {"agent": "agent_france_travail", "platform": "france_travail",
            "offers_count": len(offers), "offers": offers, "status": "ok"}
