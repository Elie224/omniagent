"""Policy Engine : regles dynamiques contextuelles au-dessus du RBAC.

Permet de definir des regles du type :
- un agent finance ne peut agir que si balance > X
- un agent ne peut envoyer plus de N messages WhatsApp par heure
- un agent ne peut postuler qu a 5 offres par jour
- un agent est bloque si le pays est en zone de risque

Les regles sont evaluees avant l execution de chaque agent.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from threading import Lock
from typing import Any, Callable


class PolicyDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


@dataclass
class PolicyContext:
    user_id: str
    user_role: str
    agent_name: str
    module: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    country: str = "FR"
    plan: str = "free"
    balance_usd: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class PolicyResult:
    decision: PolicyDecision
    rule: str
    reason: str
    requires_approval_from: str | None = None


PolicyFn = Callable[[PolicyContext], PolicyResult | None]


class PolicyEngine:
    """Evalue un ensemble de regles. Premier DENY gagne. ALLOW par defaut."""

    def __init__(self):
        self._rules: list[tuple[str, PolicyFn, int]] = []  # (name, fn, priority)
        self._lock = Lock()
        self._rate_counters: dict[str, list[datetime]] = {}

    def register(self, name: str, fn: PolicyFn, priority: int = 100) -> None:
        with self._lock:
            self._rules.append((name, fn, priority))
            self._rules.sort(key=lambda r: r[2])

    def evaluate(self, ctx: PolicyContext) -> PolicyResult:
        with self._lock:
            rules = list(self._rules)
        for name, fn, _ in rules:
            try:
                result = fn(ctx)
                if result is None:
                    continue
                if result.decision == PolicyDecision.DENY:
                    return result
                if result.decision == PolicyDecision.REQUIRE_APPROVAL:
                    return result
            except Exception as e:
                # Une regle en erreur ne doit pas tout casser : on log et on continue
                print(f"[PolicyEngine] rule {name} failed: {e}")
        return PolicyResult(PolicyDecision.ALLOW, "default", "Aucune regle n a refuse l action")

    def check_rate_limit(self, key: str, max_per_window: int,
                          window_seconds: int = 3600) -> bool:
        """Rate limiter simple base sur les timestamps."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=window_seconds)
        with self._lock:
            events = self._rate_counters.get(key, [])
            events = [e for e in events if e > cutoff]
            if len(events) >= max_per_window:
                self._rate_counters[key] = events
                return False
            events.append(now)
            self._rate_counters[key] = events
            return True


# Regles predefinies
def rule_balance_must_be_positive(ctx: PolicyContext) -> PolicyResult | None:
    """Un agent payant (plan != free) necessite une balance > 0."""
    if ctx.plan == "free":
        return None
    if ctx.balance_usd <= 0:
        return PolicyResult(PolicyDecision.DENY, "balance_must_be_positive",
                            f"Balance negative pour le plan {ctx.plan}: {ctx.balance_usd} USD")
    return None


def rule_country_sanctioned(ctx: PolicyContext) -> PolicyResult | None:
    """Bloque les pays sous sanctions internationales (liste simplifiee)."""
    sanctioned = {"KP", "IR", "SY", "CU"}
    if ctx.country.upper() in sanctioned:
        return PolicyResult(PolicyDecision.DENY, "country_sanctioned",
                            f"Pays sous sanctions: {ctx.country}")
    return None


def rule_high_value_approval(ctx: PolicyContext) -> PolicyResult | None:
    """Actions de gros montant necessitent une approbation manuelle."""
    amount = ctx.metadata.get("amount_eur", 0)
    if ctx.module == "recouvrement" and amount > 10000:
        return PolicyResult(PolicyDecision.REQUIRE_APPROVAL, "high_value_approval",
                            f"Montant eleve: {amount} EUR, approbation requise",
                            requires_approval_from="finance_lead")
    return None


def rule_rate_limit_per_agent(ctx: PolicyContext) -> PolicyResult | None:
    """Limite le nombre d appels par agent par heure."""
    max_per_hour = ctx.metadata.get("max_per_hour", 100)
    engine = _default_engine
    key = f"{ctx.user_id}:{ctx.agent_name}"
    if not engine.check_rate_limit(key, max_per_hour):
        return PolicyResult(PolicyDecision.DENY, "rate_limit_exceeded",
                            f"Trop d appels pour {ctx.agent_name} (max {max_per_hour}/h)")
    return None


def rule_business_hours(ctx: PolicyContext) -> PolicyResult | None:
    """Pas d envoi de messages entre 21h et 8h heure locale (RGPD)."""
    if ctx.module not in {"recouvrement", "marketing"}:
        return None
    hour = ctx.timestamp.hour
    if hour >= 21 or hour < 8:
        return PolicyResult(PolicyDecision.DENY, "business_hours",
                            f"Pas d envoi entre 21h et 8h (heure actuelle: {hour}h)")
    return None


# Engine par defaut, precharge avec les regles standard
_default_engine = PolicyEngine()
_default_engine.register("balance", rule_balance_must_be_positive, priority=10)
_default_engine.register("country", rule_country_sanctioned, priority=5)
_default_engine.register("business_hours", rule_business_hours, priority=20)
_default_engine.register("high_value", rule_high_value_approval, priority=15)
_default_engine.register("rate_limit", rule_rate_limit_per_agent, priority=30)


def get_default_engine() -> PolicyEngine:
    return _default_engine


async def check(ctx: PolicyContext, engine: PolicyEngine | None = None) -> PolicyResult:
    """Helper async pour evaluer une policy."""
    eng = engine or get_default_engine()
    return eng.evaluate(ctx)