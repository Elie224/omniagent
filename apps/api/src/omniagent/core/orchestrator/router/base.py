"""Intent Router : Rule -> LLM -> Fallback.

Pipeline de routage (peu couteux par defaut, evolutif) :
  1. Rule-based (keywords) : instant, 0 cout
  2. LLM (si use_llm=True et pas de match) : fallback intelligent
  3. Fallback (UNKNOWN) : laisse l appelant decider

Le LLM est mis en cache cote `ModelRouter` : la cle de cache inclut le prompt
+ la temperature, donc 2 messages identiques coutent 1 appel API au total.
"""
from __future__ import annotations
import json
import logging
from enum import Enum

from omniagent.core.models.router import model_router, TaskType


log = logging.getLogger("orchestrator.router")


class Intent(str, Enum):
    """Intents supportes par l orchestrateur (Vague B : focus Emploi).

    SEND_REMINDER et MARKETING_WEEK ont ete retires en Vague B (focus Emploi
    uniquement). Si le router matchait un de ces mots-cles avant, il renvoie
    maintenant SEARCH_JOB_AND_APPLY si possible, sinon UNKNOWN.
    """
    SEARCH_JOB_AND_APPLY = "search_job_and_apply"
    UNKNOWN = "unknown"


# 1) Rule-based : keyword -> intent
# Vague B : seul SEARCH_JOB_AND_APPLY est gere.
KEYWORD_MAP: dict[Intent, list[str]] = {
    Intent.SEARCH_JOB_AND_APPLY: [
        "offre", "emploi", "candidature", "alternance", "stage",
        "linkedin", "indeed", "hellowork", "cv", "lettre",
        "poste", "recrute", "recruteur", "apec", "adzuna",
        "wttj", "france travail", "the muse",
    ],
}


class IntentRouter:
    """Router hybride : keywords puis LLM (optionnel)."""

    def __init__(self, use_llm: bool = True):
        self._use_llm = use_llm

    # --- API sync (utilisable hors d une coroutine) ---
    def route(self, user_message: str) -> Intent:
        """Route synchrone (keyword-based uniquement, pas d appel LLM)."""
        return self._keyword_route(user_message)

    def _keyword_route(self, user_message: str) -> Intent:
        msg = user_message.lower()
        for intent, kws in KEYWORD_MAP.items():
            if any(kw in msg for kw in kws):
                return intent
        return Intent.UNKNOWN

    # --- API async (utilise le LLM en fallback) ---
    async def aroute(self, user_message: str) -> Intent:
        """Pipeline complet : keyword -> LLM -> fallback."""
        intent = self._keyword_route(user_message)
        if intent != Intent.UNKNOWN:
            return intent
        if not self._use_llm:
            return Intent.UNKNOWN
        try:
            return await self._llm_route(user_message)
        except Exception as e:
            # Toute erreur (cle API manquante, rate limit, parse) -> UNKNOWN
            log.debug(f"LLM intent routing fallback: {e}")
            return Intent.UNKNOWN

    async def _llm_route(self, user_message: str) -> Intent:
        """Classifie via LLM. Conserve un cache cote ModelRouter pour eviter les repeats."""
        labels = ", ".join([
            Intent.SEARCH_JOB_AND_APPLY.value,
            Intent.SEND_REMINDER.value,
            Intent.MARKETING_WEEK.value,
            Intent.UNKNOWN.value,
        ])
        prompt = (
            "Classifie la requete utilisateur dans une de ces intentions : "
            + labels + ".\n"
            "Reponds UNIQUEMENT par un JSON {\"intent\": \"<valeur>\"}.\n"
            "Requete: " + user_message
        )
        resp = model_router.generate(
            user_id="intent_router",
            task=TaskType.CLASSIFICATION,
            prompt=prompt,
            max_tokens=20,
            temperature=0.0,
        )
        try:
            data = json.loads(resp.text.strip())
            value = data.get("intent", "")
        except (json.JSONDecodeError, AttributeError):
            return Intent.UNKNOWN
        for intent in Intent:
            if intent.value == value:
                return intent
        return Intent.UNKNOWN


# Singleton partage
intent_router = IntentRouter()
