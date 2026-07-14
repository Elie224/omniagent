import types

import pytest

from omniagent.agents.emploi.subagents import cv_agent


@pytest.mark.asyncio
async def test_cv_agent_falls_back_when_pdflatex_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(cv_agent, "TEMPLATE_DIR", tmp_path)

    def _missing(*args, **kwargs):
        raise FileNotFoundError("pdflatex not found")

    monkeypatch.setattr(cv_agent.subprocess, "run", _missing)

    out = await cv_agent.run({"profile": {"name": "Alice"}}, user_id="u1")

    assert out["status"] == "tex_generated"
    assert out["render_pdf"] == "pdflatex_unavailable"
    assert tmp_path.joinpath("u1_cv.tex").exists()
    assert not tmp_path.joinpath("u1_cv.pdf").exists()


@pytest.mark.asyncio
async def test_cv_agent_generates_pdf_when_pdflatex_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr(cv_agent, "TEMPLATE_DIR", tmp_path)
    monkeypatch.setenv("OMNIAGENT_ENABLE_PDF_RENDER", "1")
    monkeypatch.setattr(cv_agent, "_has_moderncv_class", lambda: True)

    def _ok(cmd, capture_output, text, check):
        tex_path = tmp_path / "u2_cv.tex"
        pdf_path = tex_path.with_suffix(".pdf")
        pdf_path.write_bytes(b"%PDF-1.4\n")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(cv_agent.subprocess, "run", _ok)

    out = await cv_agent.run({"profile": {"name": "Bob"}}, user_id="u2")

    assert out["status"] == "pdf_generated"
    assert out["render_pdf"] == "ok"
    assert tmp_path.joinpath("u2_cv.tex").exists()
    assert tmp_path.joinpath("u2_cv.pdf").exists()


@pytest.mark.asyncio
async def test_cv_agent_injects_selected_offer_into_tex(tmp_path, monkeypatch):
    monkeypatch.setattr(cv_agent, "TEMPLATE_DIR", tmp_path)

    out = await cv_agent.run(
        {
            "profile": {
                "full_name": "Alice Martin",
                "email": "alice@example.com",
                "city": "Paris",
                "skills": ["Python", "SQL"],
                "target_roles": ["Data Scientist"],
            },
            "offer": {
                "title": "Senior Data Scientist",
                "company": "ACME",
                "location": "Lyon",
                "url": "https://jobs.acme.fr/offre/123",
            },
        },
        user_id="u3",
    )

    tex = tmp_path.joinpath("u3_cv.tex").read_text(encoding="utf-8")
    assert out["status"] == "tex_generated"
    assert "Senior Data Scientist" in tex
    assert "ACME" in tex
    assert "Lyon" in tex
    assert "Alice Martin" in tex
