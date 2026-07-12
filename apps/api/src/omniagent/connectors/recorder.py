"""ConnectorRecorder : snapshot I/O pour replay exact des connecteurs.

But : rendre les appels a des connecteurs externes (LinkedIn, Pennylane,
Stripe, etc.) deterministes au replay. On wrap n importe quel connecteur
qui respecte le protocole minimal `call(name, fn, *args, **kwargs)` ou
qu on appelle directement par methode.

API :
    recorder = ConnectorRecorder()
    # Wrap un connecteur
    snapshot = await recorder.call("linkedin.search_jobs", fn, criteria)
    # En replay, restitue le snapshot sans appeler fn
    recorder.replay("linkedin.search_jobs", criteria) -> snapshot

Snapshots stockes en memoire par defaut, exportables (to_dict/from_dict)
pour persistance dans l EventStore si besoin.
"""
from __future__ import annotations
import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable


def _key(call_name: str, args: tuple, kwargs: dict) -> str:
    """Cle deterministe pour indexer un snapshot."""
    h = hashlib.sha256()
    h.update(call_name.encode("utf-8"))
    h.update(b"|")
    h.update(repr(args).encode("utf-8"))
    h.update(b"|")
    # kwargs tries par cle
    for k in sorted(kwargs.keys()):
        h.update(k.encode("utf-8"))
        h.update(b"=")
        h.update(repr(kwargs[k]).encode("utf-8"))
        h.update(b"&")
    return h.hexdigest()


@dataclass
class ConnectorSnapshot:
    """Un snapshot I/O d un connecteur."""
    call_name: str
    args: tuple
    kwargs: dict
    result: Any
    error: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "call_name": self.call_name,
            "args": list(self.args),
            "kwargs": self.kwargs,
            "result": self.result,
            "error": self.error,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
        }


class ConnectorRecorder:
    """Enregistre et restitue les I/O des connecteurs pour replay deterministe.

    Mode normal : on appelle fn et on stocke le resultat.
    Mode replay  : on restitue le snapshot sans appeler fn.
    """

    def __init__(self, replay_mode: bool = False):
        self._snapshots: dict[str, ConnectorSnapshot] = {}
        self._replay_mode = replay_mode
        self._hits = 0
        self._misses = 0

    @property
    def is_replaying(self) -> bool:
        return self._replay_mode

    def enable_replay(self) -> None:
        self._replay_mode = True

    def disable_replay(self) -> None:
        self._replay_mode = False

    def load_snapshots(self, snapshots: list[dict]) -> None:
        """Charge des snapshots depuis un export (ex: depuis l EventStore)."""
        for snap_dict in snapshots:
            snap = ConnectorSnapshot(
                call_name=snap_dict["call_name"],
                args=tuple(snap_dict["args"]),
                kwargs=snap_dict["kwargs"],
                result=snap_dict["result"],
                error=snap_dict.get("error"),
                timestamp=snap_dict.get("timestamp", ""),
                duration_ms=snap_dict.get("duration_ms", 0.0),
            )
            key = _key(snap.call_name, snap.args, snap.kwargs)
            self._snapshots[key] = snap

    def export_snapshots(self) -> list[dict]:
        return [s.to_dict() for s in self._snapshots.values()]

    async def call(
        self,
        call_name: str,
        fn: Callable[..., Awaitable[Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Appelle fn (en mode normal) ou restitue le snapshot (en mode replay).

        En mode normal : on appelle fn, on stocke le resultat dans un
        ConnectorSnapshot, on retourne le resultat.
        En mode replay : on cherche un snapshot pour (call_name, args, kwargs).
        Si trouve, on restitue (avec comptage des hits). Sinon on leve
        `KeyError` pour signaler qu il manque un snapshot.
        """
        key = _key(call_name, args, kwargs)
        if self._replay_mode:
            snap = self._snapshots.get(key)
            if snap is None:
                self._misses += 1
                raise KeyError(
                    f"ConnectorRecorder en mode replay : pas de snapshot pour "
                    f"{call_name!r} (cle {key[:16]}...)"
                )
            self._hits += 1
            if snap.error:
                raise RuntimeError(f"recorded error: {snap.error}")
            return snap.result
        # Mode normal : on appelle fn et on stocke
        import time
        t0 = time.time()
        error_msg: str | None = None
        result: Any = None
        try:
            result = await fn(*args, **kwargs)
        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            raise
        finally:
            duration_ms = (time.time() - t0) * 1000.0
            self._snapshots[key] = ConnectorSnapshot(
                call_name=call_name,
                args=args,
                kwargs=kwargs,
                result=result,
                error=error_msg,
                duration_ms=duration_ms,
            )
        return result

    @property
    def stats(self) -> dict:
        return {
            "snapshots": len(self._snapshots),
            "hits": self._hits,
            "misses": self._misses,
            "replay_mode": self._replay_mode,
        }


# Singleton global (peut etre override par app.state)
_default_recorder: ConnectorRecorder | None = None


def get_default_recorder() -> ConnectorRecorder:
    global _default_recorder
    if _default_recorder is None:
        _default_recorder = ConnectorRecorder()
    return _default_recorder


def reset_default_recorder() -> None:
    global _default_recorder
    _default_recorder = None