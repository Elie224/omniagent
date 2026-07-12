"""Templates de messages de candidature par type de contrat."""

CANDIDATE_TEMPLATES: dict[str, dict[str, str]] = {
    "stage": {
        "sujet": "Candidature stage {role} \u2014 {name}",
        "corps": (
            "Bonjour {rh_name},\n\n"
            "Je me permets de vous contacter au sujet de l''offre de stage {role} "
            "publiee par {company}. Etudiant(e) en {formation}, "
            "je suis particulierement interesse(e) par {motivation}.\n\n"
            "Vous trouverez mon CV en piece jointe. Je serais ravi(e) d''echanger "
            "avec vous sur cette opportunite.\n\nCordialement,\n{name}"
        ),
    },
    "alternance": {
        "sujet": "Candidature alternance {role} \u2014 {name}",
        "corps": (
            "Bonjour {rh_name},\n\n"
            "Actuellement en {formation} en alternance, je recherche une opportunite "
            "de {role} au sein de {company}. Votre entreprise correspond a mon projet "
            "professionnel pour {motivation}.\n\nMon CV est en piece jointe. "
            "Disponible pour un echange.\n\nBien cordialement,\n{name}"
        ),
    },
    "emploi": {
        "sujet": "Candidature {role} \u2014 {name}",
        "corps": (
            "Bonjour {rh_name},\n\n"
            "Votre offre de {role} chez {company} a retenu toute mon attention. "
            "Fort(e) de {experience}, je suis convaincu(e) de pouvoir apporter "
            "{value_proposition} a vos equipes.\n\n"
            "CV en piece jointe, je serais disponible pour un entretien.\n\n"
            "Cordialement,\n{name}"
        ),
    },
}


def render_application(contract_type: str, variables: dict) -> dict:
    """Retourne {sujet, corps} pour le type de contrat demande."""
    tpl = CANDIDATE_TEMPLATES.get(contract_type, CANDIDATE_TEMPLATES["emploi"])
    return {
        "sujet": tpl["sujet"].format(**variables),
        "corps": tpl["corps"].format(**variables),
    }