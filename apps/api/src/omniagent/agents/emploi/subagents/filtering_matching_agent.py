"""Filtering + Matching Agent.

Filtre les offres selon les criteres de mission puis calcule un score de
compatibilite profil<->offre. Ne remonte que les offres au-dessus d'un seuil.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unicodedata
from typing import Any
import re


def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) >= 3]


def _vocabulary(tokens_a: list[str], tokens_b: list[str]) -> list[str]:
    return sorted(set(tokens_a) | set(tokens_b))


def _vector(tokens: list[str], vocab: list[str]) -> dict[int, float]:
    s = set(tokens)
    return {i: 1.0 for i, t in enumerate(vocab) if t in s}


def _cosine(v1: dict[int, float], v2: dict[int, float]) -> float:
    if not v1 or not v2:
        return 0.0
    common = set(v1.keys()) & set(v2.keys())
    if not common:
        return 0.0
    dot = sum(v1[i] * v2[i] for i in common)
    n1 = sum(w * w for w in v1.values()) ** 0.5
    n2 = sum(w * w for w in v2.values()) ** 0.5
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


def _profile_text(profile: dict[str, Any]) -> str:
    parts: list[str] = []
    skills = profile.get("skills") or []
    if isinstance(skills, list) and skills:
        parts.append(" ".join(str(s) for s in skills))

    target_roles = profile.get("target_roles") or profile.get("previous_roles") or []
    if isinstance(target_roles, list) and target_roles:
        parts.append(" ".join(str(r) for r in target_roles))

    formation = profile.get("formation") or profile.get("education") or ""
    if formation:
        parts.append(str(formation))

    city = profile.get("city") or ""
    if city:
        parts.append(str(city))

    return " ".join(parts).strip()


def _offer_text(offer: dict[str, Any]) -> str:
    return " ".join(
        [
            str(offer.get("title") or ""),
            str(offer.get("company") or ""),
            str(offer.get("description") or ""),
            str(offer.get("location") or ""),
            str(offer.get("contract") or ""),
        ]
    )


def _is_recent_enough(posted_at: str, recency_hours: int) -> bool:
    if recency_hours <= 0:
        return True
    if not posted_at:
        return True
    try:
        dt = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return True
    cutoff = datetime.now(timezone.utc) - timedelta(hours=recency_hours)
    return dt >= cutoff


def _location_match(location: str, city: str, radius: str) -> bool:
    if not city.strip():
        return True
    radius_norm = (radius or "city").lower().strip()
    if radius_norm == "france":
        return True
    return city.lower() in (location or "").lower()


def _contract_match(offer_contract: str, wanted_contract: str) -> bool:
    wanted = (wanted_contract or "all").strip().lower()
    if wanted in ("", "all"):
        return True
    text = (offer_contract or "").lower()
    if wanted == "emploi":
        return "stage" not in text and "altern" not in text
    if wanted == "alternance":
        return "altern" in text
    if wanted == "stage":
        return "stage" in text
    return wanted in text


def _compute_match_score(offer: dict[str, Any], profile: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    profile_text = _profile_text(profile)
    profile_tokens = _tokenize(profile_text)
    offer_tokens = _tokenize(_offer_text(offer))

    profile_empty = len(profile_tokens) == 0
    if profile_empty:
        semantic = 0.5
    else:
        vocab = _vocabulary(profile_tokens, offer_tokens)
        semantic = _cosine(_vector(profile_tokens, vocab), _vector(offer_tokens, vocab))

    user_skills = [str(s).lower() for s in (profile.get("skills") or [])]
    title = f"{offer.get('title', '')} {offer.get('company', '')}".lower()
    skill_hits = sum(1 for s in user_skills if s and s in title)
    boosted = min(1.0, semantic + 0.08 * skill_hits)

    return round(boosted, 3), {
        "semantic": round(semantic, 3),
        "skill_hits": skill_hits,
        "profile_empty": profile_empty,
    }


def _norm_text(value: str) -> str:
    base = unicodedata.normalize("NFKD", value or "")
    no_accents = "".join(ch for ch in base if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", no_accents.lower()).strip()


def _offer_dedupe_key(offer: dict[str, Any]) -> str:
    title = _norm_text(str(offer.get("title") or ""))
    company = _norm_text(str(offer.get("company") or ""))
    location = _norm_text(str(offer.get("location") or ""))
    return f"{title}|{company}|{location}"


def _dedupe_offers(offers: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    by_key: dict[str, dict[str, Any]] = {}
    duplicates = 0
    for o in offers:
        key = _offer_dedupe_key(o)
        prev = by_key.get(key)
        if prev is None:
            by_key[key] = o
            continue
        duplicates += 1
        prev_score = float(prev.get("score") or prev.get("match_score") or 0.0)
        cur_score = float(o.get("score") or o.get("match_score") or 0.0)
        if cur_score > prev_score or (cur_score == prev_score and o.get("url") and not prev.get("url")):
            by_key[key] = o
    return list(by_key.values()), duplicates


async def run(input_data: dict, user_id: str) -> dict:
    offers = input_data.get("offers") or []
    profile = input_data.get("profile") or {}

    city = str(input_data.get("city") or "").strip()
    radius = str(input_data.get("radius") or "city").strip().lower()
    contract = str(input_data.get("contract") or "all").strip().lower()
    recency_hours = int(input_data.get("recency_hours") or 0)
    score_threshold = float(input_data.get("score_threshold") or 0.45)
    max_results = int(input_data.get("max_results") or 20)

    deduped_input, duplicate_count = _dedupe_offers([dict(o) for o in offers])
    scored_offers: list[dict[str, Any]] = []
    rejected = {
        "city": 0,
        "contract": 0,
        "recency": 0,
        "score": 0,
    }

    for raw in deduped_input:
        offer = dict(raw)
        if not _location_match(str(offer.get("location") or ""), city, radius):
            rejected["city"] += 1
            continue
        if not _contract_match(str(offer.get("contract") or ""), contract):
            rejected["contract"] += 1
            continue
        if not _is_recent_enough(str(offer.get("posted_at") or ""), recency_hours):
            rejected["recency"] += 1
            continue

        score, breakdown = _compute_match_score(offer, profile)
        offer["match_score"] = score
        offer["match_breakdown"] = breakdown
        if score < score_threshold:
            rejected["score"] += 1
            continue
        scored_offers.append(offer)

    scored_offers.sort(key=lambda o: float(o.get("match_score") or 0.0), reverse=True)
    kept = scored_offers[:max_results]

    return {
        "agent": "agent_filtering_matching",
        "status": "ok",
        "inputs_consumed": ["offers", "profile", "city", "radius", "contract", "recency_hours", "score_threshold", "max_results"],
        "outputs_produced": {
            "offers": kept,
            "count_input": len(offers),
            "count_after_dedup": len(deduped_input),
            "duplicates_removed": duplicate_count,
            "count_kept": len(kept),
            "score_threshold": score_threshold,
            "rejected": rejected,
        },
    }
