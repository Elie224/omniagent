"""Agent APEC : utilise le connecteur plateforme apec."""
import logging
from typing import Any

from omniagent.connectors.manager import connector_manager


logger = logging.getLogger(__name__)


def _resolve_criteria(input_data: dict) -> dict:
    """Le runner passe `{"step": input_template, "context": ctx}`.
    On essaie de recuperer les criteres depuis step.criteria puis context.
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
    """Recherche d offres sur apec via le connecteur dedie."""
    criteria = _resolve_criteria(input_data)
    if not criteria or not criteria.get("keywords") and not criteria.get("query"):
        return {"agent": "agent_apec", "platform": "apec",
                "offers": [], "status": "no_criteria"}
    connector = connector_manager.get("apec")
    if connector is None:
        logger.warning("apec connector not registered")
        return {"agent": "agent_apec", "platform": "apec",
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
        logger.warning("apec search failed: %s", e)
        return {"agent": "agent_apec", "platform": "apec",
                "offers": [], "status": "error", "error": str(e)}
    return {"agent": "agent_apec", "platform": "apec",
            "offers_count": len(offers), "offers": offers, "status": "ok"}
