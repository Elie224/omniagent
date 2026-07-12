"""Value Object : Identifier (UUID4 string)."""
from __future__ import annotations
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class Identifier:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError("Identifier doit etre une str")
        # Validation stricte UUID4 (sans forcer la version)
        try:
            uuid.UUID(self.value)
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Identifier invalide (pas un UUID): {self.value!r}") from e

    @classmethod
    def new(cls) -> "Identifier":
        return cls(str(uuid.uuid4()))

    def __str__(self) -> str:
        return self.value
