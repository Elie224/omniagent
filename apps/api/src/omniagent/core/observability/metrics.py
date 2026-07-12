"""Compteurs et jauges pour la supervision (agent runs, taux d''erreur, couts)."""
import threading
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class Counter:
    name: str
    _value: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def inc(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value += amount

    @property
    def value(self) -> float:
        with self._lock:
            return self._value


@dataclass
class Gauge:
    name: str
    _value: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def set(self, value: float) -> None:
        with self._lock:
            self._value = value

    @property
    def value(self) -> float:
        with self._lock:
            return self._value


class MetricsRegistry:
    def __init__(self):
        self._counters: dict[str, Counter] = defaultdict(lambda: Counter(name="auto"))
        self._gauges: dict[str, Gauge] = defaultdict(lambda: Gauge(name="auto"))
        self._lock = threading.Lock()

    def counter(self, name: str) -> Counter:
        with self._lock:
            if name not in self._counters:
                self._counters[name] = Counter(name=name)
            return self._counters[name]

    def gauge(self, name: str) -> Gauge:
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = Gauge(name=name)
            return self._gauges[name]

    def snapshot(self) -> dict:
        return {
            "counters": {k: v.value for k, v in self._counters.items()},
            "gauges":   {k: v.value for k, v in self._gauges.items()},
        }


metrics = MetricsRegistry()