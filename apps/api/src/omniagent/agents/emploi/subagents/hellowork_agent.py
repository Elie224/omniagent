"""Agent Hellowork : utilise browser_service.SearchJobTool (jamais Playwright direct)."""
import sys
_BROWSER_OK = False
SearchJobTool = None  # type: ignore
try:
    sys.path.insert(0, r"C:\Users\KOURO\omniagent\packages\browser-svc\src")
    from browser_service.tools import SearchJobTool  # type: ignore
    _BROWSER_OK = True
except Exception:
    pass

_tool = SearchJobTool(platform="hellowork") if _BROWSER_OK else None

async def run(input_data: dict, user_id: str) -> dict:
    """Agent d'extraction d'offres pour hellowork.
    Fallback gracieux si browser_service indisponible.
    """
    criteria = input_data.get("criteria") or {}
    if not criteria:
        return {"agent": "agent_hellowork", "offers": [], "status": "no_criteria"}
    if not _BROWSER_OK or _tool is None:
        return {"agent": "agent_hellowork", "status": "unavailable",
                "error": "browser_service manquant (packages/browser-svc)"}
    offers = await _tool.search(user_id, criteria)
    return {"agent": "agent_hellowork", "platform": "hellowork",
            "offers_count": len(offers), "offers": offers, "status": "ok"}
