"""Agent Contact Enrichment : trouve emails/telephones publics d'une entreprise.

Strategie :
1) Extraire d'abord depuis l'offre (description, URL).
2) Scanner quelques pages publiques du site (contact, mentions).
3) Enrichir via Hunter.io si HUNTER_API_KEY est configuree.
"""
from __future__ import annotations

import os
import re
import socket
import ipaddress
from html import unescape
from typing import Any
from urllib.parse import urlparse

import httpx

from omniagent.agents.emploi.contact_finder import ContactFinder


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        key = v.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(v.strip())
    return out


def _normalize_phone(raw: str) -> str | None:
    txt = raw.strip()
    digits = re.sub(r"\D", "", txt)
    if len(digits) < 8 or len(digits) > 15:
        return None
    if txt.startswith("+"):
        return "+" + digits
    if len(digits) == 10 and digits.startswith("0"):
        # format FR basique
        return "+33" + digits[1:]
    return digits


def _extract_contacts(text: str) -> tuple[list[str], list[str]]:
    if not text:
        return [], []
    raw_emails = [m.group(0) for m in EMAIL_RE.finditer(text)]
    raw_phones = [m.group(0) for m in PHONE_RE.finditer(text)]
    phones = [p for p in (_normalize_phone(v) for v in raw_phones) if p]
    return _unique(raw_emails), _unique(phones)


def _extract_domain(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def _candidate_urls(offer_url: str, domain: str, max_pages: int) -> list[str]:
    out: list[str] = []
    if offer_url:
        out.append(offer_url)
    if domain:
        roots = [
            f"https://{domain}",
            f"https://www.{domain}",
        ]
        paths = ["", "/contact", "/nous-contacter", "/contact-us", "/mentions-legales"]
        for root in roots:
            for p in paths:
                out.append(root + p)
    return _unique(out)[:max_pages]


def _is_public_ip(ip: str) -> bool:
    try:
        obj = ipaddress.ip_address(ip)
        return bool(obj.is_global)
    except Exception:
        return False


def _resolves_to_public_ips(host: str, scheme: str) -> bool:
    port = 443 if scheme == "https" else 80
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except Exception:
        return False
    ips: set[str] = set()
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        ip = str(sockaddr[0])
        ips.add(ip)
    if not ips:
        return False
    return all(_is_public_ip(ip) for ip in ips)


def _is_safe_public_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").strip().lower()
    if scheme not in {"https"}:
        return False
    if not host or host in {"localhost", "127.0.0.1", "::1"}:
        return False
    # Hostname IP literal -> validation directe ; sinon resolution DNS.
    if _is_public_ip(host):
        return True
    return _resolves_to_public_ips(host, scheme)


async def _scan_public_pages(urls: list[str]) -> tuple[list[str], list[str], list[str]]:
    emails: list[str] = []
    phones: list[str] = []
    scanned: list[str] = []
    if not urls:
        return emails, phones, scanned

    headers = {"User-Agent": "OmniAgent/1.0 (+contact-enrichment)"}
    safe_urls = [u for u in urls if _is_safe_public_url(u)]
    async with httpx.AsyncClient(timeout=8.0, follow_redirects=False, headers=headers) as client:
        for url in safe_urls:
            try:
                r = await client.get(url)
                if r.status_code >= 400:
                    continue
                scanned.append(url)
                body = unescape(r.text or "")
                e, p = _extract_contacts(body)
                emails.extend(e)
                phones.extend(p)
            except Exception:
                continue
    return _unique(emails), _unique(phones), scanned


async def run(input_data: dict, user_id: str) -> dict:
    offer = input_data.get("offer") or {}
    company = str(input_data.get("company") or offer.get("company") or "").strip()
    offer_url = str(offer.get("url") or input_data.get("offer_url") or "").strip()
    company_domain = str(input_data.get("company_domain") or _extract_domain(offer_url) or "").strip()
    max_pages = int(input_data.get("max_pages") or 5)
    max_pages = max(1, min(max_pages, 10))

    if not company and not offer_url and not company_domain:
        return {
            "agent": "agent_contact_enrichment",
            "status": "no_company",
            "inputs_consumed": ["offer"],
            "outputs_produced": {
                "company": "",
                "company_domain": "",
                "emails": [],
                "phones": [],
                "primary_email": None,
                "primary_phone": None,
                "sources": [],
            },
        }

    description = str(offer.get("description") or "")
    desc_emails, desc_phones = _extract_contacts(description)

    candidate_urls = _candidate_urls(offer_url, company_domain, max_pages)
    web_emails, web_phones, scanned_urls = await _scan_public_pages(candidate_urls)

    hunter_email = None
    hunter_key = os.getenv("HUNTER_API_KEY", "").strip()
    # Safety: do not leak/use Anthropic secrets against Hunter API by mistake.
    if hunter_key.startswith("sk-ant"):
        hunter_key = ""
    if hunter_key and company:
        try:
            finder = ContactFinder(hunter_api_key=hunter_key)
            hunter_res = await finder.find_hr_email(company=company, company_domain=company_domain or None)
            if hunter_res and hunter_res.get("email"):
                hunter_email = str(hunter_res["email"])
        except Exception:
            hunter_email = None

    emails = _unique((([hunter_email] if hunter_email else []) + desc_emails + web_emails))
    phones = _unique(desc_phones + web_phones)

    return {
        "agent": "agent_contact_enrichment",
        "status": "ok",
        "inputs_consumed": ["offer"],
        "outputs_produced": {
            "company": company,
            "company_domain": company_domain,
            "emails": emails,
            "phones": phones,
            "primary_email": emails[0] if emails else None,
            "primary_phone": phones[0] if phones else None,
            "sources": [
                *( ["hunter"] if hunter_email else [] ),
                *( ["offer_description"] if (desc_emails or desc_phones) else [] ),
                *( ["public_web_pages"] if (web_emails or web_phones) else [] ),
            ],
            "scanned_urls": scanned_urls,
        },
    }
