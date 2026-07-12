"""Agent Emploi : coordinateur. Decide quels sous-agents lancer en parallele."""
import asyncio


async def run(input_data: dict, user_id: str) -> dict:
    """Lance les recherches LinkedIn + Indeed + HelloWork en parallele."""
    criteria = input_data.get("criteria") or input_data.get("step", {}).get("criteria") or {}
    # En prod : appeler l''AgentManager.run() pour chaque specialiste
    # Ici on retourne la structure de coordination pour la demo
    return {
        "coordinator": "agent_emploi",
        "criteria": criteria,
        "dispatched": [
            "agent_linkedin", "agent_indeed", "agent_hellowork",
            "agent_adzuna", "agent_france_travail", "agent_wttj",
        ],
        "next": "wait_results",
    }