"""Gestionnaire de sessions persistantes chiffrees."""
import json
from pathlib import Path
from typing import Any


class SessionManager:
    """Sauvegarde/charge les cookies et localStorage entre les runs."""

    def __init__(self, storage_dir: str = "./data/sessions"):
        self.path = Path(storage_dir)
        self.path.mkdir(parents=True, exist_ok=True)

    def save(self, user_id: str, platform: str, state: dict[str, Any]) -> None:
        p = self.path / f"{user_id}_{platform}.json"
        p.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def load(self, user_id: str, platform: str) -> dict[str, Any] | None:
        p = self.path / f"{user_id}_{platform}.json"
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))