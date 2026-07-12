"""Connexion SQLAlchemy async.

En mode `OMNIAGENT_FORCE_MEMORY=1`, on n ouvre aucune connexion reelle a la base.
`SessionLocal` devient un context manager no-op qui fournit une `AsyncSession`
bidon que les repos in-memory ignorent completement (ils prennent juste
l argument comme un placeholder et n executent aucune requete SQL).
"""
import os
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from omniagent.core.config import settings


_FORCE_MEMORY = os.getenv("OMNIAGENT_FORCE_MEMORY", "").lower() in ("1", "true", "yes")


class Base(DeclarativeBase):
    pass


class _NullSession:
    """Faux objet session : accepte tout, ignore tout (mode FORCE_MEMORY)."""

    async def execute(self, *args, **kwargs):
        return None

    async def commit(self):
        return None

    async def rollback(self):
        return None

    async def close(self):
        return None

    async def flush(self):
        return None

    async def refresh(self, *args, **kwargs):
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None


if _FORCE_MEMORY:
    class _NullSessionFactory:
        """Remplace `async_sessionmaker` quand FORCE_MEMORY=1."""

        def __call__(self, *args, **kwargs):
            return _NullSession()

        async def __aenter__(self):
            return _NullSession()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    SessionLocal = _NullSessionFactory()
    engine = None
else:
    engine = create_async_engine(settings.database_url, echo=settings.debug, future=True)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db():
    """Pour FastAPI Depends. No-op si FORCE_MEMORY, vraie session sinon."""
    if _FORCE_MEMORY:
        yield _NullSession()
        return
    async with SessionLocal() as session:
        yield session
