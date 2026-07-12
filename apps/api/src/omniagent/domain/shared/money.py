"""Value Object : Money (montant + devise).

Stocker en Decimal (jamais en float) pour eviter les erreurs d arrondi.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum


class Currency(str, Enum):
    EUR = "EUR"
    USD = "USD"
    GBP = "GBP"
    CHF = "CHF"


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: Currency = Currency.EUR

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            # On force la conversion (perte possible si float -> Decimal)
            object.__setattr__(self, "amount", Decimal(str(self.amount)))
        if self.amount < 0:
            raise ValueError(f"Money amount ne peut pas etre negatif: {self.amount}")
        if not isinstance(self.currency, Currency):
            try:
                object.__setattr__(self, "currency", Currency(self.currency))
            except ValueError as e:
                raise ValueError(f"Currency inconnue: {self.currency!r}") from e

    # --- Factories ---
    @classmethod
    def from_cents(cls, cents: int, currency: Currency = Currency.EUR) -> "Money":
        return cls(Decimal(cents) / Decimal(100), currency)

    @classmethod
    def from_float(cls, value: float, currency: Currency = Currency.EUR) -> "Money":
        return cls(Decimal(str(value)), currency)

    @classmethod
    def zero(cls, currency: Currency = Currency.EUR) -> "Money":
        return cls(Decimal("0"), currency)

    # --- Operations ---
    def _check_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise ValueError(
                f"Devises incompatibles: {self.currency.value} vs {other.currency.value}"
            )

    def __add__(self, other: "Money") -> "Money":
        self._check_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._check_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __mul__(self, factor: int | float | Decimal) -> "Money":
        f = Decimal(str(factor))
        return Money(self.amount * f, self.currency)

    def __lt__(self, other: "Money") -> bool:
        self._check_currency(other)
        return self.amount < other.amount

    def __le__(self, other: "Money") -> bool:
        self._check_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: "Money") -> bool:
        self._check_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: "Money") -> bool:
        self._check_currency(other)
        return self.amount >= other.amount

    # --- Serialisation ---
    def to_cents(self) -> int:
        """Convertit en centimes (entier). Utile pour stockage / Stripe."""
        return int((self.amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    def to_float(self) -> float:
        return float(self.amount)

    def to_dict(self) -> dict:
        return {"amount": str(self.amount), "currency": self.currency.value}

    def __str__(self) -> str:
        return f"{self.amount:.2f} {self.currency.value}"
