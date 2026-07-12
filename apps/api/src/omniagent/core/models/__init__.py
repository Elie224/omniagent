"""Router de modeles LLM avec quotas et couts."""

async def init_db() -> None:
    """Cree les tables manquantes. Pour la prod, preferer Alembic."""
    from omniagent.core.database import engine, Base
    # Importer les modeles pour les enregistrer dans Base.metadata
    from omniagent.core.models import db  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
