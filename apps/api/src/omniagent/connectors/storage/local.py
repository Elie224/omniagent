"""Stockage local (a remplacer par S3 / GCS en prod)."""
from pathlib import Path

from omniagent.connectors.base.connector import Connector


class LocalStorageConnector(Connector):
    name = "local_storage"
    category = "storage"

    def __init__(self, base_path: str = "./data/storage"):
        self._base = Path(base_path)
        self._base.mkdir(parents=True, exist_ok=True)

    async def health_check(self) -> bool:
        return self._base.exists()

    async def put(self, key: str, data: bytes) -> str:
        path = self._base / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)

    async def get(self, key: str) -> bytes:
        return (self._base / key).read_bytes()

    async def close(self) -> None:
        return None