"""Value Object : PhoneNumber (E.164 recommande).

Stocke la forme canonique (chiffres uniquement, prefixe +).
Valide qu il y a au moins 8 chiffres.
"""
from __future__ import annotations
import re
from dataclasses import dataclass


_DIGITS_RE = re.compile(r"\D+")


@dataclass(frozen=True)
class PhoneNumber:
    value: str  # forme canonique: +33... ou 0033...

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError("PhoneNumber doit etre une str")
        # Forme canonique : on garde +, on retire tout le reste
        raw = self.value.strip()
        if raw.startswith("00"):
            raw = "+" + raw[2:]
        digits_only = _DIGITS_RE.sub("", raw)
        if not raw.startswith("+"):
            # Heuristique FR : si 10 chiffres et commence par 0, on suppose FR
            if len(digits_only) == 10 and digits_only.startswith("0"):
                raw = "+33" + digits_only[1:]
                digits_only = "33" + digits_only[1:]
            else:
                raise ValueError(
                    f"PhoneNumber doit commencer par + ou 00 (ou etre un 0 francais): {self.value!r}"
                )
        else:
            raw = "+" + digits_only
        if len(digits_only) < 8 or len(digits_only) > 15:
            raise ValueError(f"PhoneNumber longueur invalide: {len(digits_only)} chiffres")
        object.__setattr__(self, "value", raw)

    @property
    def digits(self) -> str:
        return _DIGITS_RE.sub("", self.value)

    def masked(self) -> str:
        """Numero masque pour affichage (ex: +33*** ** ** 12)."""
        d = self.digits
        if len(d) < 4:
            return self.value
        return self.value[:3] + "***" + d[-2:]

    def __str__(self) -> str:
        return self.value
