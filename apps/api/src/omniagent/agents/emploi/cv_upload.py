"""Service d upload / extraction du CV candidat (Emploi V1).

Responsabilites :
- valider le fichier (PDF, taille max)
- le stocker via LocalStorageConnector (cle scopee par user/tenant)
- extraire un texte brut (best-effort : PyPDF2 si dispo, sinon vide)
- persister les metadonnees (filename, taille, uploaded_at, extrait texte)
  dans la memoire user sous la cle `cv:current`

API : voir `upload_cv`, `get_cv`, `delete_cv` dans router.py.
"""
from __future__ import annotations
import re
from datetime import datetime, timezone
from typing import Any

from omniagent.connectors.manager import connector_manager


MAX_SIZE_BYTES = 5 * 1024 * 1024   # 5 MB
ALLOWED_CONTENT_TYPES = {"application/pdf"}
ALLOWED_EXTENSIONS = {".pdf"}

CV_META_KEY = "cv:current"


def validate_upload(filename: str | None, content_type: str | None,
                     size_bytes: int | None) -> None:
    """Leve ValueError si le fichier n est pas valide."""
    if not filename:
        raise ValueError("filename manquant")
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"extension non supportee : {ext}. Attendu : PDF.")
    if content_type and content_type.lower() not in ALLOWED_CONTENT_TYPES:
        # Certains navigateurs envoient application/octet-stream. On accepte si
        # l extension est OK et la taille OK.
        if content_type.lower() != "application/octet-stream":
            raise ValueError(f"content-type invalide : {content_type}")
    if size_bytes is None or size_bytes <= 0:
        raise ValueError("fichier vide")
    if size_bytes > MAX_SIZE_BYTES:
        raise ValueError(f"fichier trop gros ({size_bytes} > {MAX_SIZE_BYTES})")


def validate_pdf_content(data: bytes) -> None:
    """Validation defensive du contenu PDF.

    - signature PDF attendue
    - rejet des marqueurs JS/OpenAction les plus courants
    """
    if not data.startswith(b"%PDF-"):
        raise ValueError("contenu invalide: signature PDF manquante")

    # Analyse binaire simple et rapide pour bloquer les payloads actifs frequents.
    probe = data[:2_000_000].lower()
    blocked_markers = [b"/openaction", b"/javascript", b"/js", b"/aa"]
    if any(m in probe for m in blocked_markers):
        raise ValueError("PDF actif detecte (OpenAction/JavaScript interdit)")


def extract_pdf_text(data: bytes) -> str:
    """Best-effort extraction texte d un PDF. Renvoie "" si rien d utilisable.

    On essaie PyPDF2 (lib legere, souvent dispo). Si pas dispo, on renvoie
    juste la taille + nom du fichier : l utilisateur peut toujours completer
    son profil a la main et la generation CV adaptera le LaTeX.
    """
    text_parts: list[str] = []
    try:
        import PyPDF2  # type: ignore
        import io
        reader = PyPDF2.PdfReader(io.BytesIO(data))
        for page in reader.pages[:10]:  # limite a 10 pages pour eviter l explosion
            try:
                t = page.extract_text() or ""
                if t:
                    text_parts.append(t)
            except Exception:
                continue
    except ImportError:
        return ""
    except Exception:
        return ""
    full = "\n".join(text_parts)
    # Nettoyage : on garde les mots, on collapse les espaces
    full = re.sub(r"\s+", " ", full).strip()
    return full[:8000]  # cap a 8k caracteres pour la persistance


def make_storage_key(user_id: str, tenant_id: str, filename: str) -> str:
    """Construit une cle de stockage scopee par user/tenant."""
    # On sanitize le nom de fichier (pas de path traversal, pas de char speciaux)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", filename)[:80]
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"cvs/{tenant_id}/{user_id}/{ts}_{safe}"


async def upload_cv(filename: str, content_type: str | None,
                     data: bytes, user_id: str, tenant_id: str) -> dict:
    """Valide, stocke et persiste les metadonnees du CV. Renvoie le dict CV."""
    validate_upload(filename, content_type, len(data))
    validate_pdf_content(data)
    storage = connector_manager.get("local_storage")
    if storage is None:
        raise RuntimeError("local_storage connector indisponible")
    key = make_storage_key(user_id, tenant_id, filename)
    stored_path = await storage.put(key, data)
    text_preview = extract_pdf_text(data)
    meta = {
        "filename": filename,
        "storage_key": key,
        "stored_path": stored_path,
        "size_bytes": len(data),
        "content_type": content_type or "application/pdf",
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "extracted_text_preview": text_preview[:600],  # 600 chars pour l UI
        "extracted_text_length": len(text_preview),
        "user_id": user_id,
        "tenant_id": tenant_id,
    }
    return meta


async def get_cv_meta(user_memory, user_id: str, tenant_id: str) -> dict | None:
    """Lit les metadonnees du CV courant depuis la memoire user."""
    try:
        if hasattr(user_memory, "aget"):
            return await user_memory.aget(CV_META_KEY,
                                            user_id=user_id, tenant_id=tenant_id)
        if hasattr(user_memory, "get"):
            return user_memory.get(CV_META_KEY)
    except Exception:
        return None
    return None


async def delete_cv(user_memory, storage, user_id: str, tenant_id: str) -> bool:
    """Supprime le fichier stocke + les metadonnees. Renvoie True si quelque
    chose a ete supprime."""
    meta = await get_cv_meta(user_memory, user_id, tenant_id)
    deleted_meta = False
    deleted_file = False
    try:
        if hasattr(user_memory, "adelete"):
            await user_memory.adelete(CV_META_KEY,
                                       user_id=user_id, tenant_id=tenant_id)
        elif hasattr(user_memory, "delete"):
            user_memory.delete(CV_META_KEY)
        deleted_meta = True
    except Exception:
        pass
    if meta and meta.get("storage_key") and storage is not None:
        try:
            path = meta["storage_key"]
            from pathlib import Path
            p = Path("./data/storage") / path
            if p.exists():
                p.unlink()
                deleted_file = True
        except Exception:
            pass
    return deleted_meta or deleted_file
