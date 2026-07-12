"""Agent Lettre : genere une lettre de motivation personnalisee via LLM."""


TEMPLATES = {
    "stage": (
        "Bonjour {rh_name},\n\n"
        "Actuellement en {formation}, je me permets de vous adresser ma candidature "
        "au stage {role} au sein de {company}. {motivation}\n\n"
        "Vous trouverez mon CV en piece jointe. Je reste disponible pour un echange.\n\n"
        "Cordialement,\n{name}"
    ),
    "alternance": (
        "Bonjour {rh_name},\n\n"
        "Etudiant(e) en {formation} en alternance, je souhaite rejoindre {company} "
        "pour le poste de {role}. {motivation}\n\n"
        "Mon CV est en piece jointe. Disponible pour un entretien.\n\n"
        "Bien cordialement,\n{name}"
    ),
    "emploi": (
        "Bonjour {rh_name},\n\n"
        "Votre offre de {role} chez {company} a retenu mon attention. {motivation}\n\n"
        "Fort(e) de mon experience en {experience}, je suis confiant(e) dans ma "
        "capacite a apporter de la valeur a vos equipes. CV en piece jointe.\n\n"
        "Cordialement,\n{name}"
    ),
}


async def run(input_data: dict, user_id: str) -> dict:
    contract = input_data.get("contract", "emploi")
    variables = input_data.get("variables") or {
        "rh_name": "Madame, Monsieur", "role": "votre offre",
        "company": "votre entreprise", "name": "Candidat",
        "formation": "formation en cours", "motivation": "ce poste m''interesse",
        "experience": "plusieurs annees",
    }
    tpl = TEMPLATES.get(contract, TEMPLATES["emploi"])
    body = tpl.format(**variables)
    return {"agent": "agent_lettre", "contract": contract,
            "subject": f"Candidature {variables['role']} - {variables['name']}",
            "body": body, "status": "generated"}