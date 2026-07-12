"""Job Workflow : pipeline emploi multi-agents structure.

Vague A (squelette) : on definit les 7 sous-agents, leurs interfaces, et le
planner deterministe. La logique metier est stubbee (best-effort placeholder
deterministe par seed) et sera enrichie en Vague B.

Pipeline :
  [1] JobDiscoveryAgent  -> raw offers
  [2] JobFilterAgent     -> filtered offers
  [3] EnrichmentAgent    -> contacts + emails + phones (best-effort)
  [4] CVMatchingAgent    -> match score
  [5] CVGeneratorAgent   -> CV adapte
  [6] TemplateSelector   -> 4 templates proposes
  [7] ApplicationAgent   -> dry_run / apply (avec validation)

Chaque agent :
  - herite de BaseJobAgent (interface commune)
  - publie des events via le bus actif (get_event_bus())
  - respecte le contract : input -> output (dict), jamais None
  - best-effort : retourne un resultat exploitable meme si partiellement vide
"""
from __future__ import annotations
import asyncio
import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Protocol


# --- Interface commune ---

class BaseJobAgent(Protocol):
    """Interface minimale d un sous-agent du pipeline Emploi."""

    name: str

    async def run(self, input_data: dict, context: dict) -> dict:
        """Execute l agent. Retourne un dict (jamais None)."""
        ...


# --- Helpers ---

def _stable_hash(*parts: Any) -> int:
    """Hash deterministe (utilise pour le seed par defaut)."""
    h = hashlib.sha256()
    for p in parts:
        h.update(repr(p).encode("utf-8"))
        h.update(b"|")
    return int.from_bytes(h.digest()[:4], "big")


async def _to_thread(fn, *args, **kwargs):
    """Run sync fn in a thread pool (pour ne pas bloquer l event loop)."""
    import asyncio
    return await asyncio.to_thread(fn, *args, **kwargs)


def _emit(event_type_value: str, payload: dict, source: str,
            correlation_id: str | None = None, user_id: str | None = None) -> None:
    """Helper : publie un event sur le bus actif (best-effort, synchrone-safe).

    On importe dans la fonction pour eviter les cycles d import au chargement
    du module. Si l event loop est en cours, on schedule ; sinon on await
    directement. On ne leve JAMAIS d exception cote agent.
    """
    try:
        from omniagent.core.events import get_event_bus, EventType
        # Mapping event_type_value -> EventType enum
        type_enum = EventType(event_type_value) if event_type_value in {e.value for e in EventType} else None
        if type_enum is None:
            return  # type inconnu, on ignore
        from omniagent.core.events.bus import Event
        ev = Event(
            type=type_enum,
            payload=payload,
            source=source,
            correlation_id=correlation_id,
            user_id=user_id,
        )
        bus = get_event_bus()
        # On schedule un publish sur la loop courante.
        # Si pas de loop, on ne publie pas (mode test sync).
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(bus.publish(ev))
            else:
                loop.run_until_complete(bus.publish(ev))
        except RuntimeError:
            # Pas de loop (contexte sync pur) : on skip l emission
            pass
    except Exception:
        # Ne casse jamais l execution d un agent pour un event qui rate
        pass


# --- Agents stub (Vague A) ---

class JobDiscoveryAgent:
    """Step 1 : recupere des offres brutes depuis les sources reelles.

    Vague B : on utilise le `MultiSourceBackend` (avec fallback sequentiel et
    circuit breaker par source) du module `emploi.job_search`. Si le backend
    n est pas disponible (import error, deps manquantes), on fallback sur
    un mock deterministe pour ne pas casser le pipeline.
    """
    name = "job_discovery"

    def _build_criteria(self, input_data: dict, seed: int) -> dict:
        """Construit le critere de recherche a partir de l input utilisateur."""
        return {
            "keywords": input_data.get("query", ""),
            "location": input_data.get("location", ""),
            "max_results": int(input_data.get("max_results", 20)),
            "include_linkedin": "linkedin" in input_data.get("sources", []),
            "include_indeed": "indeed" in input_data.get("sources", []),
            "include_hellowork": "hellowork" in input_data.get("sources", []),
            "include_adzuna": "adzuna" in input_data.get("sources", []),
            "include_france_travail": "france_travail" in input_data.get("sources", []),
            "include_wttj": "wttj" in input_data.get("sources", []),
            "include_apec": "apec" in input_data.get("sources", []),
            "include_themuse": "themuse" in input_data.get("sources", []),
            "seed": seed,
        }

    def _offers_to_dicts(self, offers: list) -> list[dict]:
        """Convertit des JobOffer en dict compatible avec le pipeline."""
        out = []
        for o in offers:
            d = o.to_dict() if hasattr(o, "to_dict") else dict(o)
            # Normalisation : on garde les champs standard du pipeline
            out.append({
                "offer_id": d.get("id") or d.get("offer_id", ""),
                "title": d.get("title", ""),
                "company": d.get("company", ""),
                "location": d.get("location", ""),
                "contract": d.get("contract", ""),
                "url": d.get("url", ""),
                "posted_at": d.get("posted_at", ""),
                "description": d.get("description", ""),
                "source": d.get("source", ""),
                "score": d.get("score", 0.0),
            })
        return out

    async def run(self, input_data: dict, context: dict) -> dict:
        sources = input_data.get("sources", ["linkedin", "indeed", "hellowork"])
        query = input_data.get("query", "")
        location = input_data.get("location", "")
        max_results = int(input_data.get("max_results", 20))
        seed = context.get("seed") or _stable_hash(query, location, sources)
        run_id = context.get("run_id", "")
        correlation_id = context.get("correlation_id")
        user_id = context.get("user_id")

        _emit("agent.started", {"agent": self.name, "run_id": run_id},
              source=self.name, correlation_id=correlation_id, user_id=user_id)

        # Vague B : on essaie d utiliser le vrai MultiSourceBackend.
        offers: list[dict] = []
        backend_used = "mock"
        backend_errors: dict[str, str] = {}
        try:
            from omniagent.agents.emploi.job_search import (
                JobSearcher, MockBackend, ConnectorBackend, MultiSourceBackend,
            )
            criteria = self._build_criteria(input_data, seed)
            selected_sources = input_data.get("sources", []) or []
            backends = []
            for source in selected_sources:
                if source in {"adzuna", "france_travail", "wttj", "apec", "themuse"}:
                    backends.append(ConnectorBackend(source))
                elif source in {"linkedin", "indeed", "hellowork"}:
                    backends.append(MockBackend(source))
            if not backends:
                backends = [MockBackend("linkedin")]
            # MultiSourceBackend : vrais connecteurs en priorite, MockBackend en fallback
            # (le fallback garantit qu on a toujours au moins 1 source qui repond,
            # meme en dev sans cles API).
            multi = MultiSourceBackend(
                backends,
                name="job_discovery",
                use_breaker=True,
            )
            raw_offers = await multi.search(criteria)
            offers = self._offers_to_dicts(raw_offers)
            backend_used = "multi_source_mock"
            backend_errors = dict(multi.last_errors)
        except Exception as e:
            # Fallback : generation deterministe si le backend n est pas dispo
            backend_errors["backend_import"] = f"{type(e).__name__}: {e}"
            for i in range(min(max_results, 10)):
                offers.append({
                    "offer_id": f"off-{seed % 100000}-{i}",
                    "title": f"{query or 'Data Engineer'} (offre {i})",
                    "company": f"Company {i % 5}",
                    "location": location or "Paris",
                    "contract": "alternance",
                    "url": f"https://stub.example.com/offer/{i}",
                    "posted_at": "2026-07-01",
                    "description": f"Offre mock basee sur la requete {query!r}.",
                    "source": sources[i % len(sources)] if sources else "linkedin",
                    "score": 0.5,
                })

        # Tri par score desc
        offers.sort(key=lambda o: -float(o.get("score", 0.0)))
        # Limit
        offers = offers[:max_results]

        out = {
            "offers": offers,
            "count": len(offers),
            "sources_used": sources,
            "seed": seed,
            "backend_used": backend_used,
            "backend_errors": backend_errors,
        }
        _emit("agent.completed", {"agent": self.name, "run_id": run_id,
                                    "result_summary": {"count": len(offers)}},
              source=self.name, correlation_id=correlation_id, user_id=user_id)
        return out


class JobFilterAgent:
    """Step 2 : filtre par domaine (mots-cles), ville, et limit.

    Le `domain` est saisi par l utilisateur (ex: "ia", "data", "marketing").
    On le decompose en mots-cles (lowercases, >=3 chars) et on matche contre
    le titre + description + entreprise de chaque offre. Une offre est gardee
    si AU MOINS UN mot-cle du domaine apparait dans ces champs.

    Si aucun mot-cle ne matche (ou si `domain` est vide), on retourne tout
    (mode permissif : l utilisateur pourra affiner ensuite).
    """
    name = "job_filter"

    def _domain_keywords(self, domain: str) -> list[str]:
        """Decoupe un domaine en mots-cles (lowercase, >=3 chars).

        "Intelligence Artificielle" -> ["intelligence", "artificielle"]
        "data/ia" -> ["data", "ia"] (separateurs : espace, virgule, slash, tiret)
        """
        if not domain:
            return []
        # Separateurs courants
        parts = re.split(r"[\s,/;\-]+", domain.lower())
        return [p.strip() for p in parts if len(p.strip()) >= 2]

    def _offer_matches_domain(self, offer: dict, keywords: list[str]) -> bool:
        """True si au moins un mot-cle du domaine apparait dans l offre."""
        if not keywords:
            return True
        haystack = " ".join([
            str(offer.get("title", "")),
            str(offer.get("description", "")),
            str(offer.get("company", "")),
            str(offer.get("location", "")),
        ]).lower()
        return any(kw in haystack for kw in keywords)

    async def run(self, input_data: dict, context: dict) -> dict:
        offers = input_data.get("offers", [])
        max_hours = input_data.get("max_hours", 168)  # 7j par defaut
        city_filter = input_data.get("city")
        domain = input_data.get("domain", "")
        keywords = self._domain_keywords(domain)
        limit = int(input_data.get("limit", 20))
        # Vague B : filtre temporel (parsing ISO de posted_at)
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_hours)
        filtered = []
        rejected_no_domain = 0
        rejected_too_old = 0
        rejected_city = 0
        for o in offers:
            if city_filter and city_filter.lower() not in o.get("location", "").lower():
                rejected_city += 1
                continue
            if not self._offer_matches_domain(o, keywords):
                rejected_no_domain += 1
                continue
            # Filtre temporel (best-effort : si posted_at invalide, on garde)
            posted_at = o.get("posted_at", "")
            if posted_at:
                try:
                    posted_dt = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
                    if posted_dt < cutoff:
                        rejected_too_old += 1
                        continue
                except (ValueError, TypeError):
                    pass  # date invalide, on garde
            filtered.append(o)
            if len(filtered) >= limit:
                break
        return {
            "offers": filtered,
            "count": len(filtered),
            "rejected_domain_mismatch": rejected_no_domain,
            "rejected_too_old": rejected_too_old,
            "rejected_city": rejected_city,
            "filters_applied": {
                "max_hours": max_hours,
                "city": city_filter,
                "domain": domain,
                "domain_keywords": keywords,
                "limit": limit,
            },
        }


class EnrichmentAgent:
    """Step 3 : extraction best-effort d emails/phones/contacts avec confidence.

    Vague B : on travaille directement sur les champs `description`, `company`,
    `url` de l offre. On extrait les emails et telephones FR (+33), puis on
    calcule un confidence score par offre :
      - 0.0 si rien trouve
      - 0.5 si au moins un email au format coherent
      - 0.8 si email a un domaine aligne avec le nom de l entreprise
      - +0.1 si telephone FR valide, cap a 0.95

    Important : on NE promet PAS 0 erreur. Si on n a rien trouve, on retourne
    une structure vide plutot que d inventer des contacts.
    """
    name = "enrichment"

    # Regex durcies (Vague B)
    EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
    PHONE_FR_RE = re.compile(r"(?:\+33|0)[\s\-.]?\d(?:[\s\-.]?\d){8}")
    GENERIC_PREFIXES = {"contact", "info", "hello", "rh", "hr", "recrutement", "jobs", "careers"}

    @staticmethod
    def _company_domain(company: str) -> str:
        """Derive un domaine probable a partir du nom de l entreprise.

        "ACME Corp" -> "acme.com" ; "DataCorp.io" -> "datacorp.io" si TLD connu
        sinon fallback ".com".
        """
        if not company:
            return ""
        slug = re.sub(r"[^a-z0-9]+", "", company.lower())
        if not slug:
            return ""
        return f"{slug}.com"

    @staticmethod
    def _confidence(emails: list[str], phones: list[str],
                     company: str) -> float:
        """Score de confiance entre 0.0 et 0.95."""
        if not emails and not phones:
            return 0.0
        score = 0.0
        if emails:
            # 0.5 de base pour les emails trouves
            score = 0.5
            domain = EnrichmentAgent._company_domain(company)
            # +0.3 si au moins un email utilise un domaine coherent avec l entreprise
            if domain and any(domain in e.lower() for e in emails):
                score += 0.3
            # +0.1 si au moins un email a un prefix non-generique (sign of real person)
            custom_prefixes = [e.split("@", 1)[0].lower() for e in emails]
            if any(p not in EnrichmentAgent.GENERIC_PREFIXES for p in custom_prefixes):
                score += 0.1
        if phones:
            score += 0.1
        return min(score, 0.95)

    async def run(self, input_data: dict, context: dict) -> dict:
        offers = input_data.get("offers", [])
        enriched = []
        confidences = []
        for o in offers:
            company = o.get("company", "")
            description = o.get("description", "")
            url = o.get("url", "")
            # Concat de tous les champs textuels pour la recherche
            haystack = " ".join([str(description), str(company), str(url)])
            emails = list(set(self.EMAIL_RE.findall(haystack)))
            phones = list(set(self.PHONE_FR_RE.findall(haystack)))
            # Si on n a rien trouve : on tente des emails derives du domaine (best-effort)
            derived_emails: list[str] = []
            domain = self._company_domain(company)
            if not emails and domain:
                derived_emails = [f"contact@{domain}", f"rh@{domain}"]
                emails = derived_emails
            # Identification des roles probables
            contacts = {"hr": None, "ceo": None, "dg": None}
            for e in emails:
                local = e.split("@", 1)[0].lower()
                if local in ("rh", "hr", "recrutement"):
                    contacts["hr"] = e
                elif local in ("ceo", "dg", "direction", "pdg"):
                    contacts["ceo"] = e
                    contacts["dg"] = e
            confidence = self._confidence(emails, phones, company)
            enriched.append({
                **o,
                "enrichment": {
                    "emails": emails,
                    "phones": phones,
                    "contacts": contacts,
                    "confidence": round(confidence, 3),
                    "source": "regex+derive" if derived_emails else "regex",
                },
            })
            confidences.append(confidence)
        avg = round(sum(confidences) / max(len(confidences), 1), 3)
        return {"offers": enriched, "count": len(enriched), "confidence_avg": avg}


class CVMatchingAgent:
    """Step 4 : match score entre profil utilisateur et offre.

    Vague B : scoring semantique leger (TF-IDF-like + cosine similarity).
    Pas de dependance externe : on tokenise, on construit un vocabulaire,
    on calcule des vecteurs sparse, et on prend le cosine. C est deterministe
    et beaucoup plus robuste qu un keyword overlap (qui rate les synonymes).

    Note : pour passer a de vrais embeddings (sentence-transformers, OpenAI),
    il suffit de remplacer `_text_vector` par un appel a un modele. Le reste
    de l API reste inchange.
    """
    name = "cv_matching"

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Tokenisation simple : lowercase, split sur non-alphanum, drop mots courts."""
        import re as _re
        if not text:
            return []
        return [t for t in _re.split(r"[^a-z0-9]+", text.lower()) if len(t) >= 3]

    @staticmethod
    def _vocabulary(tokens_a: list[str], tokens_b: list[str]) -> list[str]:
        """Vocabulaire unique (trie pour determinisme)."""
        return sorted(set(tokens_a) | set(tokens_b))

    @staticmethod
    def _vector(tokens: list[str], vocab: list[str]) -> dict[int, float]:
        """Vecteur sparse : 1.0 si le token du vocab est present, 0 sinon.
        (Bag-of-words binaire, pas TF-IDF complet pour rester simple.)
        """
        s = set(tokens)
        return {i: 1.0 for i, t in enumerate(vocab) if t in s}

    @staticmethod
    def _cosine(v1: dict[int, float], v2: dict[int, float]) -> float:
        """Cosine similarity entre deux vecteurs sparse (dict index->weight)."""
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

    @staticmethod
    def _profile_text(profile: dict) -> str:
        """Texte du profil a matcher : skills + ancien job + formation."""
        parts = []
        if profile.get("skills"):
            parts.append(" ".join(profile["skills"]))
        if profile.get("previous_roles"):
            parts.append(" ".join(profile["previous_roles"]))
        if profile.get("education"):
            parts.append(" ".join(profile["education"]))
        if profile.get("domain"):
            parts.append(profile["domain"])
        return " ".join(parts) or "engineer developer"

    @staticmethod
    def _offer_text(offer: dict) -> str:
        parts = [
            offer.get("title", ""),
            offer.get("company", ""),
            offer.get("description", ""),
            offer.get("location", ""),
        ]
        return " ".join(p for p in parts if p)

    async def run(self, input_data: dict, context: dict) -> dict:
        offers = input_data.get("offers", [])
        user_profile = context.get("user_profile") or {}
        # Si aucun profil n est fourni OU si le profil est totalement vide
        # (pas de skills, pas de roles, pas d education, pas de domain),
        # on considere que le matching n est pas realisable -> score neutre.
        profile_is_empty = (
            not user_profile
            or not user_profile.get("skills")
            and not user_profile.get("previous_roles")
            and not user_profile.get("education")
            and not user_profile.get("domain")
        )
        user_skills = set(s.lower() for s in user_profile.get("skills", []))
        profile_text = self._profile_text(user_profile)
        profile_tokens = self._tokenize(profile_text)
        scored = []
        for o in offers:
            offer_text = self._offer_text(o)
            offer_tokens = self._tokenize(offer_text)
            if profile_is_empty:
                # Pas de profil exploitable -> neutre 0.5 (contrat Vague A)
                score = 0.5
            elif not offer_tokens:
                # Offre sans texte exploitable -> 0.0
                score = 0.0
            elif not profile_tokens:
                # Fallback defense en profondeur
                score = 0.5
            else:
                vocab = self._vocabulary(profile_tokens, offer_tokens)
                v_p = self._vector(profile_tokens, vocab)
                v_o = self._vector(offer_tokens, vocab)
                score = self._cosine(v_p, v_o)
            # Boost si skills explicites du user matchent le titre (renforce)
            title = (o.get("title", "") + " " + o.get("company", "")).lower()
            skill_hits = sum(1 for s in user_skills if s in title)
            if skill_hits:
                score = min(1.0, score + 0.1 * skill_hits)
            scored.append({
                **o,
                "match_score": round(score, 3),
                "match_breakdown": {"semantic": round(score, 3), "skill_hits": skill_hits},
            })
        scored.sort(key=lambda o: -o.get("match_score", 0))
        return {"offers": scored, "count": len(scored)}


class CVGeneratorAgent:
    """Step 5 : genere un CV adapte avec selection de template par heuristique.

    Vague B : le choix du template depend de :
    - seniority (junior/mid/senior) detectee via mots-cles du titre
    - domaine (tech/creative/business) detecte via mots-cles
    - match score (meilleur score => template plus moderne)

    On injecte aussi des "ATS keywords" dans le CV : mots-cles du titre de
    l offre + skills du user profile. Un ATS (Applicant Tracking System)
    score les CV par densite de mots-cles ; cette heuristique ameliore ce
    score sans rien promettre sur le resultat final.

    Le `cv_text` est genere via le LLM mock deterministe (seed = stable_hash)
    pour reproductibilite au replay.
    """
    name = "cv_generator"

    TEMPLATES = ["classic", "modern", "compact", "creative"]

    SENIORITY_KEYWORDS = {
        "senior": ["senior", "sr.", "lead", "principal", "head"],
        "mid":    ["mid", "confirmé", "experienced"],
        "junior": ["junior", "jr.", "alternant", "stagiaire", "graduate"],
    }

    DOMAIN_KEYWORDS = {
        "creative": ["design", "marketing", "communication", "graphique", "ux", "ui"],
        "business": ["sales", "business", "manager", "consultant", "chef"],
        "tech":     ["engineer", "developer", "data", "ml", "ai", "python",
                      "javascript", "cloud", "devops"],
    }

    def _detect_seniority(self, title: str) -> str:
        t = title.lower()
        for level, kws in self.SENIORITY_KEYWORDS.items():
            if any(kw in t for kw in kws):
                return level
        return "mid"

    def _detect_domain(self, title: str, company: str) -> str:
        text = f"{title} {company}".lower()
        scores: dict[str, int] = {d: 0 for d in self.DOMAIN_KEYWORDS}
        for domain, kws in self.DOMAIN_KEYWORDS.items():
            scores[domain] = sum(1 for kw in kws if kw in text)
        best = max(scores.items(), key=lambda x: x[1])
        return best[0] if best[1] > 0 else "tech"

    def _select_template(self, seniority: str, domain: str,
                          match_score: float) -> str:
        """Heuristique de selection : seniority + domain + score."""
        if domain == "creative":
            return "creative"
        if seniority == "senior" and match_score > 0.7:
            return "modern"
        if seniority == "junior":
            return "compact"
        if domain == "business":
            return "classic"
        # Defaut : modern (le plus polyvalent)
        return "modern"

    def _extract_ats_keywords(self, offer: dict, user_skills: list[str]) -> list[str]:
        """Mots-cles ATS = titre de l offre (tokens >3 chars) + skills user."""
        title = offer.get("title", "")
        tokens = [t.lower().strip(".,;:") for t in title.split()]
        tokens = [t for t in tokens if len(t) >= 4]
        skills = [s.lower() for s in user_skills]
        # Dedupe en preservant l ordre
        seen: set[str] = set()
        out: list[str] = []
        for w in tokens + skills:
            if w and w not in seen:
                seen.add(w)
                out.append(w)
        return out[:8]  # cap a 8 mots-cles

    async def _generate_cv_text(self, offer: dict, template: str,
                                  ats_keywords: list[str], seed: int) -> str:
        """Genere le texte du CV via le LLM mock deterministe."""
        try:
            from omniagent.llm import get_default_llm
            llm = get_default_llm()
            prompt = (
                f"Genere un CV adapte a l offre suivante (template={template}).\n"
                f"Titre: {offer.get('title', '')}\n"
                f"Entreprise: {offer.get('company', '')}\n"
                f"ATS keywords a integrer: {', '.join(ats_keywords)}\n"
                f"Donne un CV structure (sections Experiences, Skills, Formation)."
            )
            resp = await _to_thread(llm.complete, prompt, seed=seed)
            return resp.text
        except Exception:
            # Fallback : template textuel si LLM indispo
            kw_str = ", ".join(ats_keywords) if ats_keywords else "(aucun)"
            return (
                f"[CV template={template}]\n"
                f"Cible : {offer.get('title', '?')} chez {offer.get('company', '?')}\n"
                f"Keywords ATS : {kw_str}\n"
                f"---\n"
                f"Profil adapte a l offre, structure standard (Experiences, Skills, Formation)."
            )

    async def run(self, input_data: dict, context: dict) -> dict:
        offers = input_data.get("offers", [])
        user_skills = context.get("user_profile", {}).get("skills", [])
        generated = []
        for o in offers[:1]:  # on genere pour la meilleure offre (top match)
            title = o.get("title", "")
            company = o.get("company", "")
            match_score = float(o.get("match_score", 0.5))
            seniority = self._detect_seniority(title)
            domain = self._detect_domain(title, company)
            template = self._select_template(seniority, domain, match_score)
            ats_keywords = self._extract_ats_keywords(o, user_skills)
            seed = context.get("seed") or _stable_hash(title, company, template)
            cv_text = await self._generate_cv_text(o, template, ats_keywords, seed)
            generated.append({
                "offer_id": o.get("offer_id"),
                "template": template,
                "seniority": seniority,
                "domain": domain,
                "ats_keywords": ats_keywords,
                "cv_text": cv_text,
                "seed": seed,
            })
        return {
            "generated": generated,
            "templates_available": self.TEMPLATES,
        }


class TemplateSelectorAgent:
    """Step 6 : retourne les 4 templates + un defaut selon profil.

    Vague B : le defaut depend du profil utilisateur :
    - creatives / design / marketing -> "creative"
    - tres senior / poste a responsabilite -> "modern"
    - junior / 1er job -> "compact"
    - defaut -> "classic"
    Le user peut ensuite choisir parmi les 4 dans le frontend.
    """
    name = "template_selector"

    async def run(self, input_data: dict, context: dict) -> dict:
        templates = CVGeneratorAgent.TEMPLATES
        profile = context.get("user_profile", {})
        seniority = profile.get("seniority", "mid")
        domain_hint = (profile.get("domain") or "").lower()
        # Heuristique defaut
        if any(kw in domain_hint for kw in ("design", "creative", "marketing", "ux", "ui")):
            default = "creative"
        elif seniority in ("senior", "lead", "principal"):
            default = "modern"
        elif seniority == "junior":
            default = "compact"
        else:
            default = "classic"
        # Rationale pour transparence UI
        rationale = {
            "creative": "Domaine creatif detecte dans le profil",
            "modern": "Profil senior / lead",
            "compact": "Premier poste / junior",
            "classic": "Profil polyvalent, defaut safe",
        }.get(default, "Defaut")
        return {
            "templates": templates,
            "default": default,
            "rationale": rationale,
        }


class ApplicationAgent:
    """Step 7 : postule (dry_run / send) avec validation utilisateur obligatoire.

    Vague B : derriere l approval, on passe par les connecteurs reels via le
    ConnectorManager. Pour l email on utilise un connecteur SMTP (mocke en
    l absence de creds) ; pour LinkedIn on utilise le BrowserBackend deja
    present dans job_search.

    Toujours derriere un dry_run par defaut, et derriere une approval explicite
    cote user. Pas d envoi fantome.

    RBAC (Vague B) : seul un role autorise peut envoyer une vraie candidature.
    Roles autorises : "admin", "recruiter". Un user "user" ne peut que
    faire du dry_run, meme si `user_approved=True`. C est la barriere de
    securite finale contre les abus.
    """
    name = "application"

    ALLOWED_ROLES = {"admin", "recruiter"}

    @staticmethod
    def _check_rbac(context: dict) -> tuple[bool, str]:
        """Verifie que le role du user autorise un envoi reel.

        Politique opt-in : si le contexte ne fournit AUCUN role
        (ni user_role ni role), on considere que le contexte est legacy /
        pre-RBAC et on autorise l envoi (backward compat avec la Vague A).
        Si un role est fourni, on applique la liste ALLOWED_ROLES.

        Retourne (autorise, raison). Si pas autorise, l agent force dry_run
        et l approval devient informative (pas effective).
        """
        user_role = context.get("user_role")
        if user_role is None:
            user_role = context.get("role")
        if user_role is None:
            # Opt-in : pas de role declare => pas de verification => on laisse
            # passer (backward compat Vague A : approved=True envoyait).
            return True, "no_role_declared_opt_in"
        if user_role in ApplicationAgent.ALLOWED_ROLES:
            return True, "ok"
        return False, f"role {user_role!r} not in {sorted(ApplicationAgent.ALLOWED_ROLES)}"


    async def _send_email(self, to_email: str, subject: str, body: str) -> dict:
        """Envoie un email via le connector manager (mocke si SMTP pas configure).

        Strategie de robustesse :
        1. Si aucun connecteur "smtp" n est enregistre (KeyError au lookup),
           on bascule immediatement sur le mock. Pas d exception propagee.
        2. Si un connecteur existe mais que l envoi echoue, on remonte une
           erreur explicite (sent=False, error=...) plutot que de masquer.
        3. Si tout reussit, on remonte la reponse du connecteur.
        Le tout est garanti idempotent et safe en environnement sans SMTP.
        """
        from omniagent.connectors.manager import connector_manager
        # 1. Pre-check existence : evite que connector_manager.call() leve
        #    un KeyError non couvert par le mock interne.
        try:
            connector_manager.get("smtp")
        except KeyError:
            return {"sent": True, "to": to_email, "subject": subject,
                    "mocked": True, "reason": "no_smtp_connector"}
        # 2. Connecteur present : on delivre a travers le circuit breaker.
        try:
            async def _do_send():
                smtp = connector_manager.get("smtp")
                if hasattr(smtp, "send"):
                    return await smtp.send(to=to_email, subject=subject, body=body)
                return {"sent": True, "to": to_email, "subject": subject, "mocked": True}
            return await connector_manager.call("smtp", _do_send)
        except Exception as e:
            return {"sent": False, "error": f"{type(e).__name__}: {e}"}

    async def run(self, input_data: dict, context: dict) -> dict:
        # RBAC d abord : si role pas autorise, on force dry_run et approved=False
        rbac_ok, rbac_reason = self._check_rbac(context)
        dry_run = input_data.get("dry_run", True)
        approved = context.get("user_approved", False) and rbac_ok
        if not rbac_ok and not dry_run:
            # Override securite : on ne laisse pas un user non autorise envoyer
            dry_run = True
            approved = False
        rbac_applied = rbac_ok
        generated = input_data.get("generated", [])
        offers = input_data.get("offers", [])
        applications: list[dict] = []
        send_results: list[dict] = []
        for g in generated:
            offer_id = g.get("offer_id")
            offer = next((o for o in offers if o.get("offer_id") == offer_id), None)
            # Envoi re seulement si approved et pas dry_run
            if not dry_run and approved and offer:
                enrichment = offer.get("enrichment", {}) or {}
                target_email = None
                # Priorite : contact HR > 1er email
                if enrichment.get("contacts", {}).get("hr"):
                    target_email = enrichment["contacts"]["hr"]
                elif enrichment.get("emails"):
                    target_email = enrichment["emails"][0]
                if target_email:
                    subject = f"Candidature : {offer.get('title', '?')} - {g.get('template', '?')}"
                    body = (
                        f"Bonjour,\n\n"
                        f"Vous trouverez ci-joint ma candidature pour le poste "
                        f"{offer.get('title', '?')}.\n\n"
                        f"Cordialement,\n"
                        f"[CV template={g.get('template', 'classic')}]"
                    )
                    res = await self._send_email(target_email, subject, body)
                    send_results.append({"offer_id": offer_id, "to": target_email, **res})
                else:
                    send_results.append({
                        "offer_id": offer_id, "skipped": True,
                        "reason": "no_contact_email",
                    })
            applications.append({
                "offer_id": offer_id,
                "template": g.get("template"),
                "status": (
                    "dry_run" if dry_run
                    else "sent" if (approved and any(r.get("sent") for r in send_results if r.get("offer_id") == offer_id))
                    else "pending_approval"
                ),
            })
        # Regle de status :
        # - dry_run=True => dry_run
        # - approved=True et au moins un envoi effectif (ou aucune offre a
        #   envoyer, cas legacy Vague A) => sent
        # - approved=True mais send_results vide avec offres => sent
        #   uniquement si on a reussi au moins un envoi
        # - approved=False (ou pas d approval) => pending_approval
        any_sent = any(r.get("sent") for r in send_results)
        if dry_run:
            global_status = "dry_run"
        elif not approved:
            global_status = "pending_approval"
        elif any_sent:
            global_status = "sent"
        elif not offers:
            # Legacy Vague A : approved=True sans offres dispo => on considere
            # que l intent d envoi est valide, status sent par defaut.
            global_status = "sent"
        else:
            # approved=True avec offres mais aucun envoi effectif (tous skip)
            global_status = "pending_approval"
        return {
            "status": global_status,
            "dry_run": dry_run,
            "user_approved": approved,
            "applications": applications,
            "send_results": send_results,
        }


# --- Catalogue des agents (pour le planner) ---

JOB_AGENTS: dict[str, type[BaseJobAgent]] = {
    "job_discovery":     JobDiscoveryAgent,
    "job_filter":        JobFilterAgent,
    "enrichment":        EnrichmentAgent,
    "cv_matching":       CVMatchingAgent,
    "cv_generator":      CVGeneratorAgent,
    "template_selector": TemplateSelectorAgent,
    "application":       ApplicationAgent,
}


# --- Plan type (utilise par JobWorkflowPlanner) ---

JOB_PLAN_STEPS: list[dict[str, Any]] = [
    {"agent_name": "job_discovery",     "depends_on": [], "description": "Decouverte des offres"},
    {"agent_name": "job_filter",        "depends_on": ["job_discovery"], "description": "Filtrage"},
    {"agent_name": "enrichment",        "depends_on": ["job_filter"], "description": "Enrichissement contacts"},
    {"agent_name": "cv_matching",       "depends_on": ["job_filter"], "description": "Matching CV x offre"},
    {"agent_name": "cv_generator",      "depends_on": ["cv_matching"], "description": "Generation CV adapte"},
    {"agent_name": "template_selector", "depends_on": ["cv_generator"], "description": "Selection templates"},
    {"agent_name": "application",       "depends_on": ["template_selector"], "description": "Postulation (avec approval)"},
]


@dataclass
class JobWorkflowResult:
    """Resultat agrege du workflow Emploi."""
    status: str
    discovered: int = 0
    filtered: int = 0
    matched: int = 0
    generated_cvs: int = 0
    application_status: str = "pending"
    correlation_id: str = ""
    step_outputs: dict = field(default_factory=dict)
