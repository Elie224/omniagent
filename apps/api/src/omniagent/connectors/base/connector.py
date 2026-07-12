"""Interface abstraite de tout connecteur."""
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import AsyncIterator


class Connector(ABC):
    name: str
    category: str

    @abstractmethod
    async def health_check(self) -> bool: ...

    @abstractmethod
    async def close(self) -> None: ...