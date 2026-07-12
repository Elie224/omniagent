"""Service de profil candidat (Emploi V1).

Le profil est un `Candidate` du domaine, persiste dans la memoire utilisateur
(scope user) sous la cle `profile:candidate`. Le service :

- normalise les inputs (skills split sur virgules/newlines, lowercased, dedup)
- injecte le profil dans le contexte de l orchestrateur pour que le
  CVMatchingAgent puisse scorer les offres reelles
- expose une heuristique simple pour recommander des contrats pertinents

Vague B (focus Emploi) : pas de LLM obligatoire, le profil est structure
et le matching utilise le domaine (Candidate.matches + skill overlap).
"""
from __future__ import annotations
import re
from typing import Any

from omniagent.domain.employment.entities import Candidate, ContractType


PROFILE_KEY = "profile:candidate"

# Mots-cles -> type de contrat (best-effort, pour la recommandation).
_CONTRACT_HINTS = {
    "alternance": [ContractType.ALTERNANCE],
    "alternant":  [ContractType.ALTERNANCE],
    "apprenti":   [ContractType.ALTERNANCE],
    "stage":      [ContractType.STAGE],
    "stagiaire":  [ContractType.STAGE],
    "internship": [ContractType.STAGE],
    "cdi":        [ContractType.CDI],
    "cdd":        [ContractType.CDD],
    "freelance":  [ContractType.FREELANCE],
    "independant": [ContractType.FREELANCE],
}


# ---------- Normalisation ----------

def _split_list(value: Any) -> list[str]:
    """Split une string en liste, en decoupant sur virgules / newlines / point-virgules.
    Renvoie une liste vide si l input est None ou vide.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if not isinstance(value, str):
        value = str(value)
    parts = re.split(r"[\n,;]+", value)
    return [p.strip() for p in parts if p.strip()]


def _normalize_skills(raw: Any) -> list[str]:
    """Normalise une liste de skills : lowercase, dedup, ordre preserve, drop <=1 char.
    Accepte string ("Python, SQL") ou liste (["Python", "SQL"]).
    """
    out: list[str] = []
    seen: set[str] = set()
    for s in _split_list(raw):
        s_norm = s.lower()
        if len(s_norm) <= 1:
            continue
        if s_norm in seen:
            continue
        seen.add(s_norm)
        out.append(s_norm)
    return out


def _recommend_contracts(profile: dict) -> list[ContractType]:
    """Heuristique : on regarde skills + experiences pour proposer des contrats.
    Par defaut, on propose [stage, alternance, cdi] (compat ascendante Vague A).
    On peut raffiner en Vague B+ quand on aura plus de signaux.
    """
    blob = " ".join([
        " ".join(profile.get("skills") or []),
        " ".join(str(e.get("title", "")) for e in profile.get("experiences") or []),
        profile.get("formation", ""),
    ]).lower()
    hits: set[ContractType] = set()
    for kw, contracts in _CONTRACT_HINTS.items():
        if kw in blob:
            for c in contracts:
                hits.add(c)
    if not hits:
        return [ContractType.STAGE, ContractType.ALTERNANCE, ContractType.CDI]
    # Toujours au moins CDI par defaut (donnee universelle).
    hits.add(ContractType.CDI)
    return list(hits)


# ---------- Serialisation <-> entite ----------

def profile_to_candidate(profile: dict) -> Candidate:
    """Construit un Candidate a partir du profil serialise."""
    return Candidate(
        full_name=profile.get("full_name", "") or "",
        email=profile.get("email", "") or "",
        phone=profile.get("phone", "") or "",
        formation=profile.get("formation", "") or "",
        skills=_normalize_skills(profile.get("skills")),
        experiences=profile.get("experiences") or [],
        cv_url=profile.get("cv_url", "") or "",
    )


def candidate_to_profile_payload(c: Candidate, profile: dict | None = None) -> dict:
    """Serialise un Candidate + metadata pour reponse API / persistance."""
    profile = profile or {}
    return {
        "candidate_id": c.candidate_id,
        "full_name": c.full_name,
        "email": c.email,
        "phone": c.phone,
        "formation": c.formation,
        "skills": c.skills,
        "experiences": c.experiences,
        "cv_url": c.cv_url,
        "city": profile.get("city", ""),
        "target_roles": profile.get("target_roles", []),
        "recommended_contracts": [x.value for x in _recommend_contracts({
            "skills": c.skills,
            "experiences": c.experiences,
            "formation": c.formation,
        })],
        "updated_at": profile.get("updated_at", ""),
    }


# ---------- Validation ----------

class ProfileValidationError(ValueError):
    """Erreur de validation du profil candidat."""


def validate_profile_payload(payload: dict) -> dict:
    """Valide + normalise un payload de profil (input API).
    Renvoie le profil nettoye pret a etre persiste.
    Leve ProfileValidationError si la payload est manifestement invalide.
    """
    if not isinstance(payload, dict):
        raise ProfileValidationError("payload doit etre un objet JSON")

    full_name = (payload.get("full_name") or "").strip()
    if not full_name:
        raise ProfileValidationError("full_name est obligatoire")

    skills = _normalize_skills(payload.get("skills"))
    if not skills:
        raise ProfileValidationError("au moins une skill est requise")

    formation = (payload.get("formation") or "").strip()
    experiences = payload.get("experiences") or []
    if not isinstance(experiences, list):
        raise ProfileValidationError("experiences doit etre une liste")

    return {
        "full_name": full_name,
        "email": (payload.get("email") or "").strip(),
        "phone": (payload.get("phone") or "").strip(),
        "city": (payload.get("city") or "").strip(),
        "formation": formation,
        "skills": skills,
        "target_roles": _split_list(payload.get("target_roles")),
        "experiences": [
            {k: v for k, v in (exp or {}).items() if v is not None}
            for exp in experiences
            if isinstance(exp, dict)
        ],
        "cv_url": (payload.get("cv_url") or "").strip(),
    }


# ---------- Acces memory (persistance) ----------

async def load_profile(user_memory, user_id: str, tenant_id: str) -> dict | None:
    """Charge le profil candidat depuis la memoire user. None si pas encore cree."""
    try:
        return await user_memory.aget(PROFILE_KEY, user_id=user_id, tenant_id=tenant_id)
    except Exception:
        return None


async def save_profile(user_memory, profile: dict,
                        user_id: str, tenant_id: str) -> dict:
    """Persiste le profil et renvoie la version serialisee (avec metadata).
    `profile` doit deja avoir ete valide+normalise via `validate_profile_payload`.
    Best-effort : si la DB est down (Postgres non lance), on renvoie quand meme
    le payload serialise pour que l endpoint ne retourne pas un 500.
    """
    from datetime import datetime, timezone
    profile = {**profile, "updated_at": datetime.now(timezone.utc).isoformat()}
    try:
        if hasattr(user_memory, "aset"):
            await user_memory.aset(PROFILE_KEY, profile, user_id=user_id, tenant_id=tenant_id)
        elif hasattr(user_memory, "set"):
            user_memory.set(PROFILE_KEY, profile)
    except Exception:
        # Pas de persistance (DB down / in-memory sans scope) : on continue.
        pass
    # On reconstruit un Candidate pour beneficier de la serialisation canonique.
    cand = profile_to_candidate(profile)
    return candidate_to_profile_payload(cand, profile)


# ---------- Injection dans le contexte orchestrateur ----------

def profile_to_orchestrator_context(profile: dict | None) -> dict:
    """Convertit un profil serialise en `user_profile` injectable dans le contexte
    de l orchestrateur. Le format est compatible avec CVMatchingAgent qui lit :
    - user_profile.skills   : list[str]
    - user_profile.previous_roles : list[str] (mapped from experiences[].title)
    - user_profile.education : list[str] (mapped from formation)
    - user_profile.domain    : str (1er target_role ou vide)
    """
    if not profile:
        return {}
    return {
        "candidate_id": profile.get("candidate_id", ""),
        "full_name": profile.get("full_name", ""),
        "skills": profile.get("skills", []),
        "previous_roles": [
            str(exp.get("title", "")) for exp in profile.get("experiences", [])
            if exp.get("title")
        ],
        "education": [profile.get("formation", "")] if profile.get("formation") else [],
        "domain": (profile.get("target_roles") or [""])[0],
        "city": profile.get("city", ""),
    }