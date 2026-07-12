"""Agent Indeed : utilise browser_service.SearchJobTool (jamais Playwright direct)."""
import sys
_BROWSER_OK = False
SearchJobTool = None  # type: ignore
try:
    sys.path.insert(0, r"C:\Users\KOURO\omniagent\packages\browser-svc\src")
    from browser_service.tools import SearchJobTool  # type: ignore
    _BROWSER_OK = True
except Exception:
    pass

_tool = SearchJobTool(platform="indeed") if _BROWSER_OK else None

async def run(input_data: dict, user_id: str) -> dict:
    """Agent d'extraction d'offres pour indeed.
    Fallback gracieux si browser_service indisponible.
    """
    criteria = input_data.get("criteria") or {}
    if not criteria:
        return {"agent": "agent_indeed", "offers": [], "status": "no_criteria"}
    if not _BROWSER_OK or _tool is None:
        return {"agent": "agent_indeed", "status": "unavailable",
                "error": "browser_service manquant (packages/browser-svc)"}
    offers = await _tool.search(user_id, criteria)
    return {"agent": "agent_indeed", "platform": "indeed",
            "offers_count": len(offers), "offers": offers, "status": "ok"}
