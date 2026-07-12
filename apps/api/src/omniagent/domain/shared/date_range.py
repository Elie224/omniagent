"""Value Object : DateRange (periode [start, end] inclusive)."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from typing import Union


DateLike = Union[date, datetime]


@dataclass(frozen=True)
class DateRange:
    start: DateLike
    end: DateLike

    def __post_init__(self) -> None:
        if not isinstance(self.start, (date, datetime)):
            raise TypeError("start doit etre date ou datetime")
        if not isinstance(self.end, (date, datetime)):
            raise TypeError("end doit etre date ou datetime")
        if self.end < self.start:
            raise ValueError(
                f"DateRange invalide: end ({self.end}) < start ({self.start})"
            )

    @property
    def days(self) -> int:
        s, e = self.start, self.end
        if isinstance(s, datetime) and isinstance(e, datetime):
            return (e.date() - s.date()).days
        if isinstance(s, datetime):
            s = s.date()
        if isinstance(e, datetime):
            e = e.date()
        return (e - s).days

    def contains(self, d: DateLike) -> bool:
        d_norm = d.date() if isinstance(d, datetime) else d
        s_norm = self.start.date() if isinstance(self.start, datetime) else self.start
        e_norm = self.end.date() if isinstance(self.end, datetime) else self.end
        return s_norm <= d_norm <= e_norm

    def overlaps(self, other: "DateRange") -> bool:
        return self.contains(other.start) or self.contains(other.end) or other.contains(self.start)

    def to_dict(self) -> dict:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "days": self.days,
        }

    def __str__(self) -> str:
        return f"{self.start.isoformat()} -> {self.end.isoformat()}"
