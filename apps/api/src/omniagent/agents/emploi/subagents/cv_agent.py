"""Agent CV : genere un CV adapte en LaTeX -> PDF via templates Jinja2 + pdflatex."""
import os
from pathlib import Path


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
\email{{{email}}

\begin{document}
\makecvtitle

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


async def run(input_data: dict, user_id: str) -> dict:
    profile = input_data.get("profile") or {
        "name": "Candidat", "title": "Cible", "city": "Paris", "country": "France",
        "phone": "+33600000000", "email": "c@example.com",
        "formation": "Master Informatique", "experience": "2 ans",
        "skills": "Python, SQL, Docker", "languages": "Francais, Anglais",
    }
    latex = LATEX_TEMPLATE
    for k, v in profile.items():
        latex = latex.replace("{{" + k + "}}", str(v))
    out = TEMPLATE_DIR / f"{user_id}_cv.tex"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(latex, encoding="utf-8")
    return {"agent": "agent_cv", "tex_path": str(out),
            "pdf_path": str(out).replace(".tex", ".pdf"),
            "status": "tex_generated", "render_pdf": "pdflatex (TODO)"}