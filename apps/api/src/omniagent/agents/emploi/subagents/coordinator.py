"""Agent Emploi : coordinateur. Decide quels sous-agents lancer en parallele."""


SOURCE_TO_AGENT = {
    "adzuna": "agent_adzuna",
    "france_travail": "agent_france_travail",
    "themuse": "agent_themuse",
}


async def run(input_data: dict, user_id: str) -> dict:
    """Lance les recherches selon les sources demandees."""
    criteria = input_data.get("criteria") or input_data.get("step", {}).get("criteria") or {}
    ctx = input_data.get("context") or {}
    requested_sources = criteria.get("sources") or ctx.get("sources") or ["france_travail"]
    dispatched = [SOURCE_TO_AGENT[s] for s in requested_sources if s in SOURCE_TO_AGENT]
    if not dispatched:
        dispatched = ["agent_france_travail"]
    # En prod : appeler l''AgentManager.run() pour chaque specialiste
    # Ici on retourne la structure de coordination pour la demo
    return {
        "coordinator": "agent_emploi",
        "criteria": criteria,
        "dispatched": dispatched,
        "next": "wait_results",
    }