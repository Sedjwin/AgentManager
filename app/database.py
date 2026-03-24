from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    from app import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def migrate_db():
    """Add columns introduced after initial schema creation (idempotent)."""
    from sqlalchemy import text
    stmts = [
        "ALTER TABLE agents ADD COLUMN um_user_id INTEGER",
        "ALTER TABLE agents ADD COLUMN um_api_key TEXT",
        "ALTER TABLE agents ADD COLUMN memory_tools_enabled INTEGER NOT NULL DEFAULT 1",
    ]
    async with engine.begin() as conn:
        for stmt in stmts:
            try:
                await conn.execute(text(stmt))
            except Exception:
                pass  # column already exists
