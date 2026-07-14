"""Mission Controller Agent.

Pilote le pipeline Emploi de bout en bout avec gestion des echecs partiels.
"""
from __future__ import annotations

from typing import Any

from omniagent.agents.emploi.workflow import JobDiscoveryAgent
from omniagent.agents.emploi.subagents.filtering_matching_agent import run as run_filtering_matching
from omniagent.agents.emploi.subagents.contact_enrichment_agent import run as run_contact_enrichment
from omniagent.agents.emploi.subagents.lettre_requirement_agent import run as run_lettre_requirement
from omniagent.agents.emploi.subagents.application_sender_agent import run as run_application_sender


async def _safe_step(name: str, fn):
    try:
        out = await fn()
        return {"name": name, "status": "success", "output": out, "error": None}
    except Exception as e:
        return {"name": name, "status": "failed", "output": None, "error": str(e)}


async def run(input_data: dict, user_id: str) -> dict:
    mission = input_data.get("mission") or {}
    criteria = input_data.get("criteria") or {}
    options = input_data.get("options") or {}
    profile = input_data.get("profile") or {}

    max_results = int(criteria.get("max_results") or 20)
    score_threshold = float(criteria.get("score_threshold") or 0.45)
    recency_hours = int(criteria.get("recency_hours") or 24)

    run_contact = bool(options.get("run_contact_enrichment", True))
    run_letter = bool(options.get("run_letter_generation", False))
    run_send = bool(options.get("run_application_send", False))

    steps: list[dict[str, Any]] = []
    offers = list(input_data.get("offers") or [])

    if not offers:
        async def _discover():
            discovery = JobDiscoveryAgent()
            return await discovery.run(
                {
                    "query": criteria.get("query") or mission.get("query") or "",
                    "location": criteria.get("location") or mission.get("location") or "France",
                    "radius": criteria.get("radius") or mission.get("radius") or "city",
                    "max_results": max_results,
                    "recency_hours": recency_hours,
                    "sources": criteria.get("sources") or mission.get("sources") or ["france_travail", "adzuna"],
                },
                {
                    "user_id": user_id,
                    "recency_hours": recency_hours,
                },
            )

        s = await _safe_step("discovery", _discover)
        steps.append(s)
        if s["status"] == "success":
            offers = (s["output"] or {}).get("offers") or []

    async def _filter_match():
        return await run_filtering_matching(
            {
                "offers": offers,
                "profile": profile,
                "city": criteria.get("city") or criteria.get("location") or mission.get("location") or "",
                "radius": criteria.get("radius") or mission.get("radius") or "city",
                "contract": criteria.get("contract") or "all",
                "recency_hours": recency_hours,
                "score_threshold": score_threshold,
                "max_results": max_results,
            },
            user_id=user_id,
        )

    s = await _safe_step("filtering_matching", _filter_match)
    steps.append(s)
    if s["status"] == "success":
        offers = ((s["output"] or {}).get("outputs_produced") or {}).get("offers") or []

    contact_by_offer: dict[str, dict[str, Any]] = {}
    if run_contact and offers:
        async def _enrich_batch():
            failures = 0
            for o in offers:
                try:
                    enriched = await run_contact_enrichment(
                        {
                            "offer": {
                                "title": o.get("title") or "",
                                "company": o.get("company") or "",
                                "location": o.get("location") or "",
                                "url": o.get("url") or "",
                                "description": o.get("description") or "",
                                "source": o.get("source") or "",
                                "contract": o.get("contract") or "",
                            },
                            "company": o.get("company") or "",
                            "max_pages": 3,
                        },
                        user_id=user_id,
                    )
                    key = str(o.get("offer_id") or o.get("id") or o.get("url") or o.get("title") or "")
                    contact_by_offer[key] = (enriched.get("outputs_produced") or {})
                except Exception:
                    failures += 1
            return {"contacts": contact_by_offer, "failures": failures}

        steps.append(await _safe_step("contact_enrichment", _enrich_batch))

    letter_by_offer: dict[str, dict[str, Any]] = {}
    if run_letter and offers:
        async def _letters_batch():
            failures = 0
            for o in offers:
                try:
                    letter_out = await run_lettre_requirement(
                        {"offer": o, "profile": profile},
                        user_id=user_id,
                    )
                    key = str(o.get("offer_id") or o.get("id") or o.get("url") or o.get("title") or "")
                    letter_by_offer[key] = (letter_out.get("outputs_produced") or {})
                except Exception:
                    failures += 1
            return {"letters": letter_by_offer, "failures": failures}

        steps.append(await _safe_step("letter_generation", _letters_batch))

    send_results: list[dict[str, Any]] = []
    if run_send and offers:
        async def _send_batch():
            sent = 0
            errors = 0
            for o in offers:
                key = str(o.get("offer_id") or o.get("id") or o.get("url") or o.get("title") or "")
                contact = contact_by_offer.get(key) or {}
                recruiter_email = contact.get("primary_email") or ((contact.get("emails") or [None])[0])
                if not recruiter_email:
                    send_results.append({"offer": key, "status": "no_recipient"})
                    continue
                letter = (letter_by_offer.get(key) or {}).get("letter") or {}
                try:
                    out = await run_application_sender(
                        {
                            "offer": o,
                            "profile": profile,
                            "letter": letter,
                            "recruiter_email": recruiter_email,
                        },
                        user_id=user_id,
                    )
                    produced = out.get("outputs_produced") or {}
                    send_results.append({
                        "offer": key,
                        "status": out.get("status"),
                        "recipient": produced.get("recipient"),
                        "sent": bool(produced.get("sent")),
                    })
                    if produced.get("sent"):
                        sent += 1
                except Exception:
                    errors += 1
                    send_results.append({"offer": key, "status": "send_error"})
            return {"sent": sent, "errors": errors, "results": send_results}

        steps.append(await _safe_step("application_send", _send_batch))

    failed_steps = [s for s in steps if s.get("status") != "success"]
    status = "completed" if not failed_steps else "completed_with_partial_failures"

    return {
        "agent": "agent_mission_controller",
        "status": status,
        "inputs_consumed": ["mission", "criteria", "options", "offers", "profile"],
        "outputs_produced": {
            "offers": offers,
            "steps": steps,
            "partial_failures": [
                {"step": s.get("name"), "error": s.get("error")} for s in failed_steps
            ],
            "summary": {
                "offers_count": len(offers),
                "steps_total": len(steps),
                "steps_failed": len(failed_steps),
                "applications_sent": sum(1 for x in send_results if x.get("sent")),
            },
        },
    }
