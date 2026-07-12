"""Agent France Travail : utilise le connecteur plateforme france_travail."""
import logging
from typing import Any

from omniagent.connectors.manager import connector_manager


logger = logging.getLogger(__name__)


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
        for key in ("keywords", "query", "location", "contract", "max_results"):
            if key in ctx and ctx[key] not in (None, ""):
                out.setdefault(key, ctx[key])
    return out


async def run(input_data: dict, user_id: str) -> dict:
    """Recherche d offres sur france_travail via le connecteur dedie."""
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
    try:
        offers = await connector.search(
            query=query, location=location,
            contract=contract, max_results=max_results,
        )
    except Exception as e:
        logger.warning("france_travail search failed: %s", e)
        return {"agent": "agent_france_travail", "platform": "france_travail",
                "offers": [], "status": "error", "error": str(e)}
    return {"agent": "agent_france_travail", "platform": "france_travail",
            "offers_count": len(offers), "offers": offers, "status": "ok"}
