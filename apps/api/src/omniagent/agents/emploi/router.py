"""Routes API V1 du module Emploi.

Vague B : focus Emploi. Endpoints :
  - POST /search             : recherche d offres
  - POST /apply              : declenche la generation de lettre
  - GET  /health             : healthcheck module
  - GET  /profile            : recupere le profil candidat du user
  - POST /profile            : cree / met a jour le profil candidat
  - DELETE /profile          : supprime le profil candidat
  - GET  /profile/summary    : profil + contexte orchestrateur pret a injecter
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Literal

from omniagent.auth.dependencies import CurrentUser, get_current_user, require_module_access
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
    include_linkedin: bool = True
    include_indeed: bool = True
    include_hellowork: bool = True
    max_results: int = Field(default=20, ge=1, le=100)


class SearchResponse(BaseModel):
    status: str
    total_offers: int
    by_platform: dict[str, int]
    offers_sample: list[dict]


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
    _user: CurrentUser = Depends(require_module_access("emploi", "agent_emploi")),
):
    """Recherche d offres sur les plateformes activees (delegue a l orchestrateur)."""
    return SearchResponse(status="queued", total_offers=0, by_platform={}, offers_sample=[])


@router.post("/apply")
async def apply_to_offer(
    req: ApplyRequest,
    user: CurrentUser = Depends(require_module_access("emploi", "agent_lettre")),
):
    from omniagent.agents.emploi.subagents.lettre_agent import run as run_lettre
    lettre = await run_lettre({"contract": req.contract, "variables": req.variables},
                                user_id=user.user_id)
    return {"offer_id": req.offer_id, "lettre": lettre, "status": "draft"}


@router.get("/health")
async def health():
    return {"module": "emploi", "status": "ok", "agents": [
        "agent_emploi", "agent_linkedin", "agent_indeed",
        "agent_hellowork", "agent_cv", "agent_lettre"
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
