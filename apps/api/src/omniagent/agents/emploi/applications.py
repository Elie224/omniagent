"""Service de suivi des candidatures envoyees (Emploi V1, Vague B).

Une `TrackedApplication` represente une candidature concrete envoyee (ou en
cours d envoi) par un candidat. Elle est stockee dans la memoire user sous
une liste indexee par user_id/tenant_id.

Vocation :
- permettre a l utilisateur de suivre ses candidatures (statut, date,
  contacts, etc.)
- etre la source de verite pour la fonctionnalite "Mes Candidatures" du front
- etre alimentee automatiquement quand une candidature est validee depuis
  le pipeline Emploi (sans casser les autres agents)

Design :
- format interne = dict serialisable (memes conventions que le profil)
- persistance via `user_memory.alist/aset` (ou `list/set` en fallback)
- normalisations : dates ISO, emails lowercased, phone chiffre seulement
"""
from __future__ import annotations
import re
from datetime import datetime, timezone
from typing import Any

from omniagent.domain.employment.entities import ApplicationStatus


APPLICATIONS_KEY = "applications:list"

# Statuts exposes cote frontend (mappes sur l enum du domaine).
STATUS_VALUES = [
    "draft",          # brouillon (jamais envoye)
    "sent",           # envoyee, en attente de reponse
    "viewed",         # l entreprise a vu la candidature
    "interview",      # en cours d entretien
    "accepted",       # acceptee / offre recue
    "rejected",       # refusee
    "withdrawn",      # retiree par le candidat
]


def normalize_status(s: Any) -> str:
    """Normalise un statut en une des valeurs exposees. Fallback = 'sent'."""
    if not s:
        return ApplicationStatus.SENT.value
    v = str(s).strip().lower()
    # mapping tolerant (le domaine dit 'offer', l utilisateur dit 'accepted')
    aliases = {
        "offre": "accepted",
        "offer": "accepted",
        "refuse": "rejected",
        "refusee": "rejected",
        "entretien": "interview",
        "envoyee": "sent",
        "envoye": "sent",
        "brouillon": "draft",
        "vue": "viewed",
        "annulee": "withdrawn",
        "annule": "withdrawn",
    }
    v = aliases.get(v, v)
    if v not in STATUS_VALUES:
        return ApplicationStatus.SENT.value
    return v


def normalize_email(s: Any) -> str:
    if not s:
        return ""
    return str(s).strip().lower()


def normalize_phone(s: Any) -> str:
    if not s:
        return ""
    digits = re.sub(r"\D", "", str(s))
    return digits


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_application_payload(payload: dict) -> dict:
    """Valide + normalise une candidature (input API).
    Champs obligatoires : `company`, `position`. Statut par defaut 'sent'.
    """
    if not isinstance(payload, dict):
        raise ValueError("payload doit etre un objet JSON")
    company = (payload.get("company") or "").strip()
    if not company:
        raise ValueError("company est obligatoire")
    position = (payload.get("position") or payload.get("title") or "").strip()
    if not position:
        raise ValueError("position (intitule du poste) est obligatoire")
    return {
        "company": company,
        "position": position,
        "location": (payload.get("location") or "").strip(),
        "email": normalize_email(payload.get("email")),
        "phone": normalize_phone(payload.get("phone")),
        "url": (payload.get("url") or "").strip(),
        "source": (payload.get("source") or "").strip().lower(),
        "contract": (payload.get("contract") or "").strip().lower(),
        "status": normalize_status(payload.get("status") or "sent"),
        "sent_at": (payload.get("sent_at") or utcnow_iso()),
        "updated_at": utcnow_iso(),
        "notes": (payload.get("notes") or "").strip(),
        "contact_name": (payload.get("contact_name") or "").strip(),
    }


def _coerce_app(a: dict) -> dict:
    """Re-normalise une candidature stockee (defensif, post-migration)."""
    return {
        "application_id": a.get("application_id") or "",
        "company": a.get("company", "") or "",
        "position": a.get("position", "") or a.get("title", "") or "",
        "location": a.get("location", "") or "",
        "email": normalize_email(a.get("email")),
        "phone": normalize_phone(a.get("phone")),
        "url": a.get("url", "") or "",
        "source": a.get("source", "") or "",
        "contract": a.get("contract", "") or "",
        "status": normalize_status(a.get("status")),
        "sent_at": a.get("sent_at") or "",
        "updated_at": a.get("updated_at") or "",
        "notes": a.get("notes", "") or "",
        "contact_name": a.get("contact_name", "") or "",
    }


# ---------- Acces memory (persistance) ----------

async def list_applications(user_memory, user_id: str, tenant_id: str) -> list[dict]:
    """Renvoie toutes les candidatures du user, triees par `sent_at` desc.

    La liste est stockee sous une seule cle `applications:list` (un dict avec
    `items: [...]`). On lit directement par `aget`, pas par `alist` (qui
    retournerait uniquement les cles prefixees, pas la liste interne).
    """
    items = await _load_payload(user_memory, user_id, tenant_id)
    items.sort(key=lambda x: x.get("sent_at") or "", reverse=True)
    return items


async def _save_list(user_memory, apps: list[dict],
                      user_id: str, tenant_id: str) -> None:
    """Persiste la liste complete sous un indexe scope (un row par application).
    On utilise `applications:list:<application_id>` pour eviter les collisions
    avec d autres listes.
    """
    scoped_key = APPLICATIONS_KEY
    payload = {"items": [_coerce_app(a) for a in apps]}
    try:
        if hasattr(user_memory, "aset"):
            await user_memory.aset(scoped_key, payload, user_id=user_id, tenant_id=tenant_id)
        elif hasattr(user_memory, "set"):
            user_memory.set(scoped_key, payload)
    except Exception:
        pass


async def _load_payload(user_memory, user_id: str, tenant_id: str) -> list[dict]:
    """Lit le payload `{items: [...]}` depuis la memory, ou liste vide."""
    try:
        if hasattr(user_memory, "aget"):
            data = await user_memory.aget(APPLICATIONS_KEY, user_id=user_id, tenant_id=tenant_id)
        elif hasattr(user_memory, "get"):
            data = user_memory.get(APPLICATIONS_KEY)
        else:
            return []
    except Exception:
        return []
    if not data or not isinstance(data, dict):
        return []
    items = data.get("items") or []
    return [_coerce_app(a) for a in items if isinstance(a, dict)]


async def add_application(user_memory, payload: dict,
                           user_id: str, tenant_id: str) -> dict:
    """Ajoute une candidature et renvoie la version serialisee."""
    from uuid import uuid4
    app = validate_application_payload(payload)
    app["application_id"] = str(uuid4())
    current = await _load_payload(user_memory, user_id, tenant_id)
    current.insert(0, app)
    await _save_list(user_memory, current, user_id, tenant_id)
    return app


async def update_application(user_memory, application_id: str,
                              patch: dict,
                              user_id: str, tenant_id: str) -> dict | None:
    """Patch une candidature. Renvoie la version mise a jour ou None si inconnue."""
    current = await _load_payload(user_memory, user_id, tenant_id)
    found = None
    for i, a in enumerate(current):
        if a.get("application_id") == application_id:
            merged = {**a}
            for k, v in (patch or {}).items():
                if k == "status":
                    merged["status"] = normalize_status(v)
                elif k == "email":
                    merged["email"] = normalize_email(v)
                elif k == "phone":
                    merged["phone"] = normalize_phone(v)
                else:
                    if v is not None:
                        merged[k] = v
            merged["updated_at"] = utcnow_iso()
            current[i] = merged
            found = merged
            break
    if found is None:
        return None
    await _save_list(user_memory, current, user_id, tenant_id)
    return found


async def delete_application(user_memory, application_id: str,
                              user_id: str, tenant_id: str) -> bool:
    current = await _load_payload(user_memory, user_id, tenant_id)
    new = [a for a in current if a.get("application_id") != application_id]
    if len(new) == len(current):
        return False
    await _save_list(user_memory, new, user_id, tenant_id)
    return True


# ---------- Pont avec l orchestrateur ----------

def build_application_from_orchestrator(offer: dict, profile: dict | None,
                                          contact: dict | None = None) -> dict:
    """Construit une candidature a partir d une offre validee par l utilisateur.
    Utilise quand le pipeline Emploi detecte une candidature 'validee'.
    """
    profile = profile or {}
    contact = contact or {}
    return validate_application_payload({
        "company": offer.get("company") or "",
        "position": offer.get("title") or "",
        "location": offer.get("location") or profile.get("city", ""),
        "url": offer.get("url") or "",
        "source": offer.get("source") or "",
        "contract": offer.get("contract") or "",
        "status": "sent",
        "email": contact.get("email") or "",
        "phone": contact.get("phone") or "",
        "contact_name": contact.get("name") or "",
    })
