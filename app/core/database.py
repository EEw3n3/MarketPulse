from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.core.config import settings

# pool_pre_ping: Postgres-critical — tests connections before use,
# preventing "SSL connection closed unexpectedly" errors after idle periods.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

# Session factory — one per application lifetime
async_session_maker = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db() -> None:
    """
    Creates all tables that don't yet exist.
    For schema *changes* use Alembic migrations (alembic upgrade head).
    """
    # Import all models so SQLModel.metadata knows about them
    from app.domain.models import (  # noqa: F401
        Product, ProductGroup, ScrapingRule, PriceHistory, SharedPattern
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


@asynccontextmanager
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session