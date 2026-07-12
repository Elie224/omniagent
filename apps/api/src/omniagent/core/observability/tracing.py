"""Traceur d''execution des agents (compatible OpenTelemetry)."""
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class Span:
    name: str
    started_at: float
    finished_at: float | None = None
    attributes: dict = field(default_factory=dict)
    parent: str | None = None
    children: list[str] = field(default_factory=list)

    def duration_ms(self) -> float:
        if self.finished_at is None:
            return 0.0
        return (self.finished_at - self.started_at) * 1000


class Tracer:
    """Traceur en memoire (remplaceable par OpenTelemetry / LangSmith)."""

    def __init__(self):
        self._spans: dict[str, Span] = {}
        self._current: str | None = None

    @contextmanager
    def span(self, name: str, **attrs) -> Iterator[Span]:
        sid = f"{name}_{int(time.time() * 1_000_000)}"
        sp = Span(name=name, started_at=time.time(), attributes=attrs, parent=self._current)
        if self._current:
            self._spans[self._current].children.append(sid)
        self._spans[sid] = sp
        prev = self._current
        self._current = sid
        try:
            yield sp
        finally:
            sp.finished_at = time.time()
            self._current = prev

    def get(self, span_id: str) -> Span | None:
        return self._spans.get(span_id)

    def all(self) -> list[Span]:
        return list(self._spans.values())


tracer = Tracer()