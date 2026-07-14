"""Routes API V1 du module Emploi.

Vague B : focus Emploi. Endpoints :
  - POST /search             : recherche d offres
  - POST /apply              : declenche la generation de lettre
  - GET  /health             : healthcheck module
    - POST /cv/generate        : genere un CV (tex/pdf) via agent_cv
    - GET  /cv/generated/download : telecharge le PDF genere par agent_cv
  - GET  /profile            : recupere le profil candidat du user
  - POST /profile            : cree / met a jour le profil candidat
  - DELETE /profile          : supprime le profil candidat
  - GET  /profile/summary    : profil + contexte orchestrateur pret a injecter
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Literal
from collections import Counter

from omniagent.auth.dependencies import CurrentUser, get_current_user, require_module_access
from omniagent.core.config import settings
from omniagent.agents.emploi.profile import (
    ProfileValidationError,
    candidate_to_profile_payload,
    load_profile,
    profile_to_candidate,
    profile_to_orchestrator_context,
    save_profile,
    validate_profile_payload,
)
from omniagent.agents.emploi.applications import (
    STATUS_VALUES,
    add_application,
    delete_application,
    list_applications,
    update_application,
    validate_application_payload,
)
from omniagent.agents.emploi.cv_upload import (
    CV_META_KEY,
    delete_cv,
    get_cv_meta,
    upload_cv,
)


router = APIRouter()


# ---------- Models API ----------

class SearchCriteria(BaseModel):
    keywords: str
    location: str = "France"
    contract: Literal["stage", "alternance", "emploi", "all"] = "all"
    include_france_travail: bool = True
    include_linkedin: bool = True
    include_indeed: bool = True
    include_hellowork: bool = True
    max_results: int = Field(default=20, ge=1, le=100)


class SearchResponse(BaseModel):
    status: str
    total_offers: int
    by_platform: dict[str, int]
    offers_sample: list[dict]
    backend_used: str | None = None
    backend_errors: dict[str, str] = Field(default_factory=dict)


class ApplyRequest(BaseModel):
    offer_id: str
    contract: Literal["stage", "alternance", "emploi"] = "emploi"
    variables: dict = Field(default_factory=dict)


class ExperienceItem(BaseModel):
    title: str = ""
    company: str = ""
    years: int | None = None
    description: str = ""


class ProfileRequest(BaseModel):
    full_name: str = ""
    email: str = ""
    phone: str = ""
    city: str = ""
    formation: str = ""
    skills: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    experiences: list[ExperienceItem] = Field(default_factory=list)
    cv_url: str = ""


class ApplicationRequest(BaseModel):
    company: str = ""
    position: str = ""
    location: str = ""
    email: str = ""
    phone: str = ""
    url: str = ""
    source: str = ""
    contract: str = ""
    status: str = "sent"
    sent_at: str = ""
    notes: str = ""
    contact_name: str = ""


class ApplicationPatch(BaseModel):
    company: str | None = None
    position: str | None = None
    location: str | None = None
    email: str | None = None
    phone: str | None = None
    url: str | None = None
    source: str | None = None
    contract: str | None = None
    status: str | None = None
    notes: str | None = None
    contact_name: str | None = None


class CVGenerateRequest(BaseModel):
    offer: dict = Field(default_factory=dict)
    template: str = "moderne"


# ---------- Helpers ----------

def _get_user_memory(request: Request):
    """Recupere le user memory du stack memoire (sync ou async)."""
    stack = getattr(request.app.state, "memory_stack", None)
    if stack is None:
        raise HTTPException(
            status_code=503,
            detail="Memory stack indisponible (app mal initialisee)",
        )
    return stack.user


async def _aget(user_mem, key: str, user_id: str, tenant_id: str):
    """Lecture unifiee : supporte UserMemory (async) et InMemoryUserMemory (sync).
    Best-effort : toute erreur (DB down, etc.) est capturee et retournee comme
    "profil absent" plutot que de faire tomber l endpoint.
    """
    try:
        if hasattr(user_mem, "aget"):
            return await user_mem.aget(key, user_id=user_id, tenant_id=tenant_id)
        # InMemoryUserMemory : pas de notion de user/tenant, fallback sur get().
        return user_mem.get(key)
    except Exception:
        return None


async def _aset(user_mem, key: str, value: dict, user_id: str, tenant_id: str):
    try:
        if hasattr(user_mem, "aset"):
            await user_mem.aset(key, value, user_id=user_id, tenant_id=tenant_id)
            return
        user_mem.set(key, value)
    except Exception:
        # On laisse remonter : un echec d ecriture doit etre visible a l appelant.
        raise


async def _adelete(user_mem, key: str, user_id: str, tenant_id: str):
    try:
        if hasattr(user_mem, "adelete"):
            await user_mem.adelete(key, user_id=user_id, tenant_id=tenant_id)
            return
        user_mem.delete(key)
    except Exception:
        raise


# ---------- Endpoints existants ----------

@router.post("/search", response_model=SearchResponse)
async def search_offers(
    criteria: SearchCriteria,
    user: CurrentUser = Depends(require_module_access("emploi", "agent_emploi")),
):
    """Recherche d offres sur les plateformes activees.

    Route legere pour recuperer des offres sans declencher tout le workflow.
    Reutilise l agent de discovery afin de garder le meme comportement que
    l orchestrateur, y compris France Travail et les fallbacks de dev.
    """
    from omniagent.agents.emploi.workflow import JobDiscoveryAgent

    sources: list[str] = []
    if criteria.include_france_travail:
        sources.append("france_travail")
    if criteria.include_linkedin:
        sources.append("linkedin")
    if criteria.include_indeed:
        sources.append("indeed")
    if criteria.include_hellowork:
        sources.append("hellowork")
    if not sources:
        raise HTTPException(status_code=400, detail="aucune source activee")

    discovery = JobDiscoveryAgent()
    result = await discovery.run(
        {
            "query": criteria.keywords,
            "location": criteria.location,
            "contract": criteria.contract,
            "max_results": criteria.max_results,
            "sources": sources,
        },
        {
            "tenant_id": user.tenant_id,
            "user_id": user.user_id,
        },
    )
    offers = result.get("offers") or []
    by_platform = dict(Counter((o.get("source") or "unknown") for o in offers))
    return SearchResponse(
        status="ok",
        total_offers=len(offers),
        by_platform=by_platform,
        offers_sample=offers[: min(len(offers), criteria.max_results)],
        backend_used=result.get("backend_used"),
        backend_errors=result.get("backend_errors") or {},
    )


@router.post("/apply")
async def apply_to_offer(
    req: ApplyRequest,
    user: CurrentUser = Depends(require_module_access("emploi", "agent_lettre")),
):
    """Compat legacy: genere une lettre via agent_lettre."""
    from omniagent.agents.emploi.subagents.lettre_agent import run as run_lettre
    lettre = await run_lettre({"contract": req.contract, "variables": req.variables},
                                user_id=user.user_id)
    return {"offer_id": req.offer_id, "lettre": lettre, "status": "draft"}


@router.post("/lettre/generate", dependencies=[Depends(require_module_access("emploi", "agent_lettre"))])
async def generate_lettre(req: ApplyRequest,
                          user: CurrentUser = Depends(get_current_user)):
    """Endpoint explicite pour agent_lettre (separe de tout envoi)."""
    from omniagent.agents.emploi.subagents.lettre_agent import run as run_lettre
    lettre = await run_lettre({"contract": req.contract, "variables": req.variables},
                                user_id=user.user_id)
    return {"offer_id": req.offer_id, "lettre": lettre, "status": "draft"}


@router.get("/health")
async def health():
    return {"module": "emploi", "status": "ok", "agents": [
        "agent_emploi", "agent_adzuna", "agent_france_travail",
        "agent_themuse", "agent_cv", "agent_lettre"
    ]}


# ---------- Profil candidat (Vague B) ----------

@router.get("/profile")
async def get_profile(request: Request,
                       user: CurrentUser = Depends(get_current_user)):
    """Recupere le profil candidat du user courant. 404 si pas encore cree."""
    user_mem = _get_user_memory(request)
    profile = await _aget(user_mem, "profile:candidate",
                           user_id=user.user_id, tenant_id=user.tenant_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profil non initialise")
    cand = profile_to_candidate(profile)
    return candidate_to_profile_payload(cand, profile)


@router.post("/profile")
async def upsert_profile(req: ProfileRequest, request: Request,
                          user: CurrentUser = Depends(get_current_user)):
    """Cree ou met a jour le profil candidat du user courant.

    Valide et normalise (skills lowercased + dedup, experiences filtrees,
    full_name obligatoire, au moins 1 skill). Renvoie le profil serialise.
    """
    try:
        profile = validate_profile_payload(req.model_dump())
    except ProfileValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    user_mem = _get_user_memory(request)
    saved = await save_profile(user_mem, profile,
                                user_id=user.user_id, tenant_id=user.tenant_id)
    return {"status": "ok", "profile": saved}


@router.delete("/profile")
async def delete_profile(request: Request,
                          user: CurrentUser = Depends(get_current_user)):
    """Supprime le profil candidat du user courant (idempotent)."""
    user_mem = _get_user_memory(request)
    await _adelete(user_mem, "profile:candidate",
                    user_id=user.user_id, tenant_id=user.tenant_id)
    return {"status": "ok", "deleted": True}


@router.get("/profile/summary")
async def profile_summary(request: Request,
                           user: CurrentUser = Depends(get_current_user)):
    """Renvoie le profil + le contexte orchestrateur pret a etre injecte.

    Utile cote frontend pour visualiser ce qui sera envoye au pipeline Emploi.
    Renvoie 404 si pas de profil.
    """
    user_mem = _get_user_memory(request)
    profile = await _aget(user_mem, "profile:candidate",
                           user_id=user.user_id, tenant_id=user.tenant_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profil non initialise")
    cand = profile_to_candidate(profile)
    return {
        "profile": candidate_to_profile_payload(cand, profile),
        "orchestrator_context": profile_to_orchestrator_context(profile),
    }


# ---------- Suivi des candidatures (Vague B) ----------

@router.get("/applications")
async def list_my_applications(request: Request,
                                user: CurrentUser = Depends(get_current_user)):
    """Liste toutes les candidatures suivies par le user courant."""
    user_mem = _get_user_memory(request)
    items = await list_applications(user_mem,
                                     user_id=user.user_id, tenant_id=user.tenant_id)
    return {"status": "ok", "count": len(items), "applications": items}


@router.post("/applications")
async def create_application(req: ApplicationRequest, request: Request,
                             user: CurrentUser = Depends(get_current_user)):
    """Ajoute une candidature au suivi du user. Renvoie l application serialisee."""
    try:
        validated = validate_application_payload(req.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    user_mem = _get_user_memory(request)
    saved = await add_application(user_mem, validated,
                                   user_id=user.user_id, tenant_id=user.tenant_id)
    return {"status": "ok", "application": saved}


@router.patch("/applications/{application_id}")
async def patch_application(application_id: str, req: ApplicationPatch,
                             request: Request,
                             user: CurrentUser = Depends(get_current_user)):
    """Patche une candidature (status, notes, contact). Renvoie la version mise a jour."""
    patch = {k: v for k, v in req.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=422, detail="Patch vide")
    user_mem = _get_user_memory(request)
    updated = await update_application(user_mem, application_id, patch,
                                       user_id=user.user_id, tenant_id=user.tenant_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Candidature introuvable")
    return {"status": "ok", "application": updated}


@router.delete("/applications/{application_id}")
async def remove_application(application_id: str, request: Request,
                              user: CurrentUser = Depends(get_current_user)):
    """Supprime une candidature du suivi. Idempotent."""
    user_mem = _get_user_memory(request)
    deleted = await delete_application(user_mem, application_id,
                                        user_id=user.user_id, tenant_id=user.tenant_id)
    return {"status": "ok", "deleted": deleted}


# ---------- Upload CV (PDF) ----------

@router.post("/cv/upload")
async def upload_cv_endpoint(request: Request,
                              user: CurrentUser = Depends(get_current_user)):
    """Upload un CV au format PDF. Stocke sur disque + persiste les metadonnees
    (texte extrait si PyPDF2 dispo) dans la memoire user.

    Body : multipart/form-data avec un champ `file` (PDF, max 5 MB).
    """
    from fastapi import HTTPException, UploadFile, File
    # Diagnostic : logger les requetes entrantes pour identifier d eventuels
    # POST automatiques (HMR, hot reload, etc.). A retirer en prod.
    import logging
    logging.getLogger("cv_upload").warning(
        "[CV UPLOAD] POST from UA=%r Referer=%r content_type=%r",
        request.headers.get("user-agent", "?"),
        request.headers.get("referer", "?"),
        request.headers.get("content-type", "?"),
    )
    user_mem = _get_user_memory(request)
    # On lit le form manuellement (compatibilite avec FastAPI UploadFile).
    form = await request.form()
    upload = form.get("file")
    # Defensive: requete sans partie fichier (HMR / prefetch / cycle).
    if upload is None or not hasattr(upload, "read"):
        return {"status": "no_file", "cv": None}
    # UploadFile ou FileField : on recupere filename/content_type/data
    filename = getattr(upload, "filename", None)
    content_type = getattr(upload, "content_type", None)
    data = await upload.read() if hasattr(upload, "read") else b""
    try:
        meta = await upload_cv(filename or "cv.pdf", content_type, data,
                                user_id=user.user_id, tenant_id=user.tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur upload: {e}")
    # On persiste les metadonnees dans la memoire user (best-effort)
    try:
        if hasattr(user_mem, "aset"):
            await user_mem.aset(CV_META_KEY, meta,
                                 user_id=user.user_id, tenant_id=user.tenant_id)
        elif hasattr(user_mem, "set"):
            user_mem.set(CV_META_KEY, meta)
    except Exception:
        pass
    return {"status": "ok", "cv": meta}


@router.get("/cv")
async def get_cv_endpoint(request: Request,
                           user: CurrentUser = Depends(get_current_user)):
    """Renvoie les metadonnees du CV courant du user (404 si pas encore uploade)."""
    user_mem = _get_user_memory(request)
    meta = await get_cv_meta(user_mem, user_id=user.user_id, tenant_id=user.tenant_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Aucun CV uploade")
    return {"status": "ok", "cv": meta}


@router.delete("/cv")
async def delete_cv_endpoint(request: Request,
                              user: CurrentUser = Depends(get_current_user)):
    """Supprime le CV courant du user (fichier + metadonnees). Idempotent."""
    user_mem = _get_user_memory(request)
    from omniagent.connectors.manager import connector_manager
    storage = connector_manager.get("local_storage")
    deleted = await delete_cv(user_mem, storage,
                                user_id=user.user_id, tenant_id=user.tenant_id)
    return {"status": "ok", "deleted": deleted}


@router.get("/cv/download")
async def download_cv_endpoint(request: Request,
                                user: CurrentUser = Depends(get_current_user)):
    """Telecharge le fichier PDF du CV courant (pour preview / re-use)."""
    from fastapi import HTTPException
    from fastapi.responses import FileResponse
    user_mem = _get_user_memory(request)
    meta = await get_cv_meta(user_mem, user_id=user.user_id, tenant_id=user.tenant_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Aucun CV uploade")
    stored_path = meta.get("stored_path")
    if not stored_path:
        raise HTTPException(status_code=404, detail="Fichier introuvable")
    from pathlib import Path
    p = Path(stored_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Fichier physique manquant")
    return FileResponse(path=str(p), media_type="application/pdf",
                         filename=meta.get("filename", "cv.pdf"))


@router.post("/cv/generate")
async def generate_cv_endpoint(request: Request,
                                req: CVGenerateRequest,
                                user: CurrentUser = Depends(get_current_user)):
    """Genere un CV via agent_cv (LaTeX -> PDF si pdflatex est disponible)."""
    from omniagent.agents.emploi.subagents.cv_agent import run as run_cv_agent

    user_mem = _get_user_memory(request)
    profile = await _aget(
        user_mem,
        "profile:candidate",
        user_id=user.user_id,
        tenant_id=user.tenant_id,
    ) or {}
    out = await run_cv_agent(
        {"profile": profile, "offer": req.offer, "template": req.template},
        user_id=user.user_id,
    )
    return {"status": "ok", **out}


@router.get("/cv/generated/download")
async def download_generated_cv_endpoint(user: CurrentUser = Depends(get_current_user)):
    """Telecharge le PDF genere par l agent CV pour l utilisateur courant."""
    from pathlib import Path
    from fastapi import HTTPException
    from fastapi.responses import FileResponse
    from omniagent.agents.emploi.subagents.cv_agent import TEMPLATE_DIR

    pdf_path = Path(TEMPLATE_DIR) / f"{user.user_id}_cv.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="CV PDF non genere")
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"{user.user_id}_cv.pdf",
    )


# ---------- Sprint 3b : 3 nouveaux agents (interview, salary, followup) ----------

class InterviewCoachRequest(BaseModel):
    offer: dict = Field(default_factory=dict)
    profile: dict = Field(default_factory=dict)


@router.post("/interview/prepare", dependencies=[Depends(require_module_access("emploi", "agent_interview_coach"))])
async def interview_prepare(req: InterviewCoachRequest,
                             user: CurrentUser = Depends(get_current_user)):
    """Prepare le candidat a un entretien (questions, pitch, red flags)."""
    from omniagent.agents.emploi.subagents.interview_coach_agent import run as run_agent
    out = await run_agent(
        {"offer": req.offer, "profile": req.profile},
        user_id=user.user_id,
    )
    # Aplatir outputs_produced pour les champs metier (match_score, themes, ...)
    produced = out.get("outputs_produced") or {}
    return {
        "status": "ok",
        "user_id": user.user_id,
        "tenant_id": user.tenant_id,
        **out,
        **produced,
    }


class SalaryBenchmarkRequest(BaseModel):
    role: str = ""
    city: str = ""
    years_experience: int = 0
    declared_salary: float | None = None


@router.post("/salary/benchmark", dependencies=[Depends(require_module_access("emploi", "agent_salary_benchmark"))])
async def salary_benchmark(req: SalaryBenchmarkRequest,
                            user: CurrentUser = Depends(get_current_user)):
    """Retourne la fourchette salariale estimee + arguments de negociation."""
    from omniagent.agents.emploi.subagents.salary_benchmark_agent import run as run_agent
    out = await run_agent(
        {"role": req.role, "city": req.city,
         "years_experience": req.years_experience,
         "declared_salary": req.declared_salary},
        user_id=user.user_id,
    )
    produced = out.get("outputs_produced") or {}
    return {
        "status": "ok",
        "user_id": user.user_id,
        "tenant_id": user.tenant_id,
        **out,
        **produced,
    }


class FollowupRequest(BaseModel):
    applications: list[dict] = Field(default_factory=list)
    profile: dict = Field(default_factory=dict)
    tone: str = "formel"
    threshold_days: int = 5


class ContactEnrichRequest(BaseModel):
    offer: dict = Field(default_factory=dict)
    company: str = ""
    company_domain: str = ""
    max_pages: int = Field(default=5, ge=1, le=10)
    user_confirmation: bool = False
    legal_basis: str = ""


class LettreAutoRequest(BaseModel):
    offer: dict = Field(default_factory=dict)
    profile: dict = Field(default_factory=dict)


class ApplicationSendRequest(BaseModel):
    offer: dict = Field(default_factory=dict)
    recruiter_email: str = ""
    letter: dict = Field(default_factory=dict)
    profile: dict = Field(default_factory=dict)
    confirm_phrase: str = ""
    force_send: bool = False


class FilteringMatchingRequest(BaseModel):
    offers: list[dict] = Field(default_factory=list)
    city: str = ""
    radius: str = "city"
    contract: Literal["stage", "alternance", "emploi", "all"] = "all"
    recency_hours: int = Field(default=24, ge=0, le=24 * 30)
    score_threshold: float = Field(default=0.45, ge=0.0, le=1.0)
    max_results: int = Field(default=20, ge=1, le=100)
    profile: dict = Field(default_factory=dict)


class MissionControllerRequest(BaseModel):
    mission: dict = Field(default_factory=dict)
    criteria: dict = Field(default_factory=dict)
    options: dict = Field(default_factory=dict)
    offers: list[dict] = Field(default_factory=list)
    profile: dict = Field(default_factory=dict)


@router.post("/followup/generate", dependencies=[Depends(require_module_access("emploi", "agent_followup"))])
async def followup_generate(req: FollowupRequest,
                             request: Request,
                             user: CurrentUser = Depends(get_current_user)):
    """Genere des emails de relance pour les candidatures J+threshold_days."""
    from omniagent.agents.emploi.subagents.followup_agent import run as run_agent
    out = await run_agent(
        {"applications": req.applications, "profile": req.profile,
         "tone": req.tone, "threshold_days": req.threshold_days},
        user_id=user.user_id,
    )
    produced = out.get("outputs_produced") or {}
    return {
        "status": "ok",
        "user_id": user.user_id,
        "tenant_id": user.tenant_id,
        **out,
        **produced,
    }


@router.post("/contact/enrich", dependencies=[Depends(require_module_access("emploi", "agent_contact_enrichment"))])
async def contact_enrich(req: ContactEnrichRequest,
                         user: CurrentUser = Depends(get_current_user)):
    """Trouve les contacts publics (email/telephone) de l entreprise de l offre."""
    if not req.user_confirmation:
        raise HTTPException(status_code=422, detail="Confirmation utilisateur explicite requise pour contact_enrich")
    allowed_basis = {"legitimate_interest", "contractual_necessity", "consent"}
    if req.legal_basis.strip().lower() not in allowed_basis:
        raise HTTPException(status_code=422, detail="legal_basis invalide: utiliser legitimate_interest|contractual_necessity|consent")
    from omniagent.agents.emploi.subagents.contact_enrichment_agent import run as run_agent
    out = await run_agent(
        {
            "offer": req.offer,
            "company": req.company,
            "company_domain": req.company_domain,
            "max_pages": req.max_pages,
        },
        user_id=user.user_id,
    )
    produced = out.get("outputs_produced") or {}
    return {
        "status": "ok",
        "user_id": user.user_id,
        "tenant_id": user.tenant_id,
        **out,
        **produced,
    }


@router.post("/lettre/auto", dependencies=[Depends(require_module_access("emploi", "agent_lettre_requirement"))])
async def lettre_auto(req: LettreAutoRequest,
                      request: Request,
                      user: CurrentUser = Depends(get_current_user)):
    """Genere une lettre uniquement si l'offre la demande explicitement."""
    from omniagent.agents.emploi.subagents.lettre_requirement_agent import run as run_agent

    profile = req.profile
    if not profile:
        user_mem = _get_user_memory(request)
        profile = await _aget(
            user_mem,
            "profile:candidate",
            user_id=user.user_id,
            tenant_id=user.tenant_id,
        ) or {}

    out = await run_agent({"offer": req.offer, "profile": profile}, user_id=user.user_id)
    produced = out.get("outputs_produced") or {}
    return {
        "status": "ok",
        "user_id": user.user_id,
        "tenant_id": user.tenant_id,
        **out,
        **produced,
    }


@router.post("/application/send", dependencies=[Depends(require_module_access("emploi", "agent_application_sender"))])
async def application_send(req: ApplicationSendRequest,
                           request: Request,
                           user: CurrentUser = Depends(get_current_user)):
    """Envoie la candidature au recruteur (email + lettre + CV si disponible)."""
    from omniagent.agents.emploi.subagents.application_sender_agent import run as run_agent

    profile = req.profile
    if not profile:
        user_mem = _get_user_memory(request)
        profile = await _aget(
            user_mem,
            "profile:candidate",
            user_id=user.user_id,
            tenant_id=user.tenant_id,
        ) or {}

    # Garde-fou doublon: evite un double envoi sur meme offre + destinataire.
    user_mem = _get_user_memory(request)
    if req.recruiter_email and not req.force_send:
        existing = await list_applications(user_mem, user_id=user.user_id, tenant_id=user.tenant_id)
        target_company = str(req.offer.get("company") or "").strip().lower()
        target_position = str(req.offer.get("title") or "").strip().lower()
        target_email = str(req.recruiter_email or "").strip().lower()
        duplicate = next((
            a for a in existing
            if str(a.get("company") or "").strip().lower() == target_company
            and str(a.get("position") or "").strip().lower() == target_position
            and str(a.get("email") or "").strip().lower() == target_email
            and str(a.get("status") or "") in ("sent", "viewed", "interview", "accepted")
        ), None)
        if duplicate:
            return {
                "status": "ok",
                "user_id": user.user_id,
                "tenant_id": user.tenant_id,
                "agent": "agent_application_sender",
                "sent": False,
                "duplicate_prevented": True,
                "duplicate_application_id": duplicate.get("application_id"),
                "message": "Envoi bloque: candidature deja envoyee pour cette offre et ce contact.",
            }

    out = await run_agent(
        {
            "offer": req.offer,
            "recruiter_email": req.recruiter_email,
            "letter": req.letter,
            "profile": profile,
            "user_confirmed": req.confirm_phrase.strip().upper() == str(settings.application_sender_confirmation_phrase or "JE CONFIRME L ENVOI").strip().upper(),
            "confirmation_phrase": req.confirm_phrase,
        },
        user_id=user.user_id,
    )
    produced = out.get("outputs_produced") or {}

    # Tracking mini-CRM: persister l action d envoi ou le brouillon.
    if req.offer:
        try:
            app_status = "sent" if produced.get("sent") else "draft"
            await add_application(
                user_mem,
                {
                    "company": req.offer.get("company") or "Entreprise",
                    "position": req.offer.get("title") or "Poste",
                    "location": req.offer.get("location") or "",
                    "url": req.offer.get("url") or "",
                    "source": req.offer.get("source") or "",
                    "contract": req.offer.get("contract") or "",
                    "status": app_status,
                    "email": req.recruiter_email or "",
                    "notes": f"application_sender_status={out.get('status')}",
                },
                user_id=user.user_id,
                tenant_id=user.tenant_id,
            )
        except Exception:
            pass

    return {
        "status": "ok",
        "user_id": user.user_id,
        "tenant_id": user.tenant_id,
        **out,
        **produced,
    }


@router.post("/offers/filter-match", dependencies=[Depends(require_module_access("emploi", "agent_filtering_matching"))])
async def offers_filter_match(req: FilteringMatchingRequest,
                              request: Request,
                              user: CurrentUser = Depends(get_current_user)):
    """Filtre les offres (ville/periode/contrat) et score la compatibilite profil."""
    from omniagent.agents.emploi.subagents.filtering_matching_agent import run as run_agent

    profile = req.profile
    if not profile:
        user_mem = _get_user_memory(request)
        profile = await _aget(
            user_mem,
            "profile:candidate",
            user_id=user.user_id,
            tenant_id=user.tenant_id,
        ) or {}

    out = await run_agent(
        {
            "offers": req.offers,
            "city": req.city,
            "radius": req.radius,
            "contract": req.contract,
            "recency_hours": req.recency_hours,
            "score_threshold": req.score_threshold,
            "max_results": req.max_results,
            "profile": profile,
        },
        user_id=user.user_id,
    )
    produced = out.get("outputs_produced") or {}
    return {
        "status": "ok",
        "user_id": user.user_id,
        "tenant_id": user.tenant_id,
        **out,
        **produced,
    }


@router.post("/mission/run", dependencies=[Depends(require_module_access("emploi", "agent_mission_controller"))])
async def mission_run(req: MissionControllerRequest,
                      request: Request,
                      user: CurrentUser = Depends(get_current_user)):
    """Pilote une mission Emploi complete avec gestion d echecs partiels."""
    from omniagent.agents.emploi.subagents.mission_controller_agent import run as run_agent

    profile = req.profile
    if not profile:
        user_mem = _get_user_memory(request)
        profile = await _aget(
            user_mem,
            "profile:candidate",
            user_id=user.user_id,
            tenant_id=user.tenant_id,
        ) or {}

    out = await run_agent(
        {
            "mission": req.mission,
            "criteria": req.criteria,
            "options": req.options,
            "offers": req.offers,
            "profile": profile,
        },
        user_id=user.user_id,
    )
    produced = out.get("outputs_produced") or {}
    return {
        "status": "ok",
        "user_id": user.user_id,
        "tenant_id": user.tenant_id,
        **out,
        **produced,
    }
