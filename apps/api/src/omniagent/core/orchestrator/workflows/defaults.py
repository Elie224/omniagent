"""Workflows par defaut enregistres au boot.

Pour en ajouter : creer une nouvelle fonction `_register_<nom>(registry)`
et l appeler depuis `register_default_workflows(registry)`.
"""
from __future__ import annotations

from .registry import WorkflowDefinition, WorkflowStep, WorkflowRegistry


def _wf_job_search_dag() -> WorkflowDefinition:
    """Pipeline complet de recherche d emploi (le plus courant)."""
    return WorkflowDefinition(
        name="job_search_dag",
        version="1.0.0",
        intent="job_workflow_run",
        description="Recherche complete puis postulation : discovery -> filter -> match -> cv -> apply.",
        tags=["emploi", "dag", "core"],
        steps=[
            WorkflowStep("discovery", "job_discovery",
                          description="Decouverte des offres (multi-sources)."),
            WorkflowStep("filter", "job_filter",
                          depends_on=["discovery"],
                          description="Filtrage des offres selon les criteres."),
            WorkflowStep("enrich", "enrichment",
                          depends_on=["filter"],
                          description="Enrichissement des metadonnees entreprise."),
            WorkflowStep("match", "cv_matching",
                          depends_on=["enrich"],
                          description="Matching CV/offre."),
            WorkflowStep("cv", "cv_generator",
                          depends_on=["match"],
                          description="Generation du CV adapte."),
            WorkflowStep("template", "template_selector",
                          depends_on=["cv"],
                          description="Selection du template de lettre."),
            WorkflowStep("apply", "application",
                          depends_on=["template"],
                          description="Envoi de la candidature."),
        ],
    )


def _wf_job_search_quick() -> WorkflowDefinition:
    """Variante rapide : discovery + filter seulement (pour scan exploratoire)."""
    return WorkflowDefinition(
        name="job_search_quick",
        version="1.0.0",
        intent="job_workflow_run",
        description="Scan exploratoire : discovery puis filter, sans postulation.",
        tags=["emploi", "quick", "scan"],
        steps=[
            WorkflowStep("discovery", "job_discovery",
                          description="Decouverte des offres."),
            WorkflowStep("filter", "job_filter",
                          depends_on=["discovery"],
                          description="Filtrage rapide."),
        ],
    )


def _wf_cv_refresh() -> WorkflowDefinition:
    """Reprise du CV + lettre sans postulation immediate."""
    return WorkflowDefinition(
        name="cv_refresh",
        version="1.0.0",
        intent="job_workflow_run",
        description="Reconstruit le CV et la lettre a partir du profil candidat.",
        tags=["emploi", "cv"],
        steps=[
            WorkflowStep("match", "cv_matching",
                          description="Re-evalue le profil vs cibles."),
            WorkflowStep("cv", "cv_generator",
                          depends_on=["match"],
                          description="Genere une nouvelle version du CV."),
            WorkflowStep("template", "template_selector",
                          depends_on=["cv"],
                          description="Selectionne le template optimal."),
        ],
    )


def _wf_intent_research() -> WorkflowDefinition:
    """Cadrage initial d une intention de recherche (avant discovery)."""
    return WorkflowDefinition(
        name="intent_research",
        version="1.0.0",
        intent="search_job_and_apply",
        description="Cadrage du besoin candidat + premiere discovery.",
        tags=["emploi", "intake"],
        steps=[
            WorkflowStep("coordinate", "agent_emploi",
                          description="Coordonne l intake."),
            WorkflowStep("linkedin", "agent_linkedin",
                          depends_on=["coordinate"],
                          description="Discovery LinkedIn."),
        ],
    )


def register_default_workflows(registry: WorkflowRegistry | None = None) -> int:
    """Enregistre tous les workflows par defaut. Retourne le nombre ajoute."""
    reg = registry or WorkflowRegistry.__new__(WorkflowRegistry)
    # Si on a recu None, on prend l instance globale
    from .registry import workflow_registry as _global
    target = reg if reg.__class__ is WorkflowRegistry and hasattr(reg, "_workflows") else _global
    builders = [
        _wf_job_search_dag,
        _wf_job_search_quick,
        _wf_cv_refresh,
        _wf_intent_research,
    ]
    added = 0
    for b in builders:
        wf = b()
        if target.exists(wf.name):
            continue
        target.register(wf)
        added += 1
    return added