"""Agent CV : genere un CV adapte en LaTeX -> PDF via templates Jinja2 + pdflatex."""
import os
import subprocess
from pathlib import Path
from typing import Any


TEMPLATE_DIR = Path(__file__).parent / "templates"


LATEX_TEMPLATE = r"""
\documentclass[11pt,a4paper]{moderncv}
\moderncvstyle{casual}
\moderncvcolor{purple}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{lmodern}

\name{{{name}}}{{}}
\title{{{title}}}
\address{{{city}}}{{country}}
\phone[mobile]{{{phone}}}
\email{{{email}}}

\begin{document}
\makecvtitle

\section{Offre cible}
{{target_offer}}

\section{Formation}
{{formation}}

\section{Experience}
{{experience}}

\section{Competences}
{{skills}}

\section{Langues}
{{languages}}
\end{document}
"""


def _coerce_text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",")]
        return [p for p in parts if p]
    return []


def _build_experience_text(profile: dict[str, Any]) -> str:
    experiences = profile.get("experiences")
    if isinstance(experiences, list) and experiences:
        lines: list[str] = []
        for exp in experiences[:5]:
            if not isinstance(exp, dict):
                continue
            title = str(exp.get("title") or "").strip()
            company = str(exp.get("company") or "").strip()
            years = exp.get("years")
            desc = str(exp.get("description") or "").strip()
            head = " - ".join([p for p in [title, company] if p]) or "Experience"
            if years not in (None, ""):
                head += f" ({years} an(s))"
            if desc:
                lines.append(f"{head}\\\\{desc}")
            else:
                lines.append(head)
        if lines:
            return "\\\\".join(lines)
    return str(profile.get("experience") or "2 ans").strip()


def _resolve_cv_profile(input_data: dict[str, Any]) -> dict[str, str]:
    profile = input_data.get("profile") or {}
    offer = input_data.get("offer") or {}

    full_name = str(profile.get("full_name") or profile.get("name") or "Candidat").strip()
    target_title = str(
        offer.get("title")
        or profile.get("title")
        or ((profile.get("target_roles") or [""])[0])
        or "Cible"
    ).strip()
    target_city = str(offer.get("location") or profile.get("city") or "Paris").strip()

    skills = _coerce_text_list(profile.get("skills"))
    if not skills:
        skills = _coerce_text_list(profile.get("skills_text"))
    skills_text = ", ".join(skills) if skills else "Python, SQL, Docker"

    languages = _coerce_text_list(profile.get("languages"))
    languages_text = ", ".join(languages) if languages else "Francais, Anglais"

    formation = str(profile.get("formation") or "Master Informatique").strip()
    experience_text = _build_experience_text(profile)

    offer_title = str(offer.get("title") or "").strip()
    offer_company = str(offer.get("company") or "").strip()
    offer_location = str(offer.get("location") or "").strip()
    offer_url = str(offer.get("url") or "").strip()
    target_offer = " - ".join([p for p in [offer_title, offer_company] if p])
    if offer_location:
        target_offer = (target_offer + f" ({offer_location})").strip()
    if not target_offer:
        target_offer = "Non specifiee"
    if offer_url:
        target_offer += f"\\\\Lien: {offer_url}"

    return {
        "name": full_name,
        "title": target_title,
        "city": target_city,
        "country": str(profile.get("country") or "France").strip(),
        "phone": str(profile.get("phone") or "+33600000000").strip(),
        "email": str(profile.get("email") or "c@invalid.invalid").strip(),
        "formation": formation,
        "experience": experience_text,
        "skills": skills_text,
        "languages": languages_text,
        "target_offer": target_offer,
    }


def _has_moderncv_class() -> bool:
    """Return True when LaTeX moderncv class is available in the TeX tree.

    This avoids triggering interactive MiKTeX package-install dialogs on Windows.
    """
    try:
        probe = subprocess.run(
            ["kpsewhich", "moderncv.cls"],
            capture_output=True,
            text=True,
            check=False,
        )
        return probe.returncode == 0
    except FileNotFoundError:
        # kpsewhich (or TeX) is not installed.
        return False


async def run(input_data: dict, user_id: str) -> dict:
    profile = _resolve_cv_profile(input_data)
    latex = LATEX_TEMPLATE
    for k, v in profile.items():
        latex = latex.replace("{{" + k + "}}", str(v))
    out = TEMPLATE_DIR / f"{user_id}_cv.tex"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(latex, encoding="utf-8")

    pdf_path = out.with_suffix(".pdf")
    status = "tex_generated"
    render_pdf = "pdflatex_unavailable"
    # Safety default: avoid triggering interactive TeX package installers
    # (notably MiKTeX popups on Windows) during normal app usage.
    if os.getenv("OMNIAGENT_ENABLE_PDF_RENDER", "0") not in {"1", "true", "TRUE", "yes", "YES"}:
        return {
            "agent": "agent_cv",
            "tex_path": str(out),
            "pdf_path": str(pdf_path),
            "status": status,
            "render_pdf": "pdflatex_unavailable",
        }

    if not _has_moderncv_class():
        return {
            "agent": "agent_cv",
            "tex_path": str(out),
            "pdf_path": str(pdf_path),
            "status": status,
            "render_pdf": "pdflatex_unavailable",
        }

    try:
        result = subprocess.run(
            [
                "pdflatex",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-output-directory",
                str(out.parent),
                str(out),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and pdf_path.exists():
            status = "pdf_generated"
            render_pdf = "ok"
        else:
            tail = (result.stderr or result.stdout or "").strip().splitlines()
            detail = tail[-1] if tail else f"exit_code={result.returncode}"
            render_pdf = f"pdflatex_failed: {detail}"
    except FileNotFoundError:
        render_pdf = "pdflatex_unavailable"

    return {
        "agent": "agent_cv",
        "tex_path": str(out),
        "pdf_path": str(pdf_path),
        "status": status,
        "render_pdf": render_pdf,
    }