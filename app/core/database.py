from contextlib import asynccontextmanager  # <-- THIS WAS MISSING
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
import os

# Get database URL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://market_user:market_password@localhost:5432/market_pulse_db")

# Create engine
engine = create_async_engine(DATABASE_URL, echo=False, future=True)

# Create session factory (better to do this globally once)
async_session_maker = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

# Decorator turns the generator function into a context manager
@asynccontextmanager
async def async_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session