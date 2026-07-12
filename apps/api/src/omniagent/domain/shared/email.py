"""Value Object : Email (valide a la construction)."""
from __future__ import annotations
import re
from dataclasses import dataclass


_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


@dataclass(frozen=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError(f"Email doit etre une str, recu: {type(self.value).__name__}")
        normalized = self.value.strip().lower()
        if not _EMAIL_RE.match(normalized):
            raise ValueError(f"Email invalide: {self.value!r}")
        object.__setattr__(self, "value", normalized)

    @property
    def domain(self) -> str:
        return self.value.split("@", 1)[1]

    @property
    def local(self) -> str:
        return self.value.split("@", 1)[0]

    def __str__(self) -> str:
        return self.value
