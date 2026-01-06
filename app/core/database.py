from contextlib import asynccontextmanager  # <-- ВОТ ЭТОГО НЕ ХВАТАЛО
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
import os

# Получаем URL базы данных
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://market_user:market_password@localhost:5432/market_pulse_db")

# Создаем движок
engine = create_async_engine(DATABASE_URL, echo=False, future=True)

# Создаем фабрику сессий (лучше делать это глобально один раз)
async_session_maker = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

# Декоратор превращает функцию-генератор в контекстный менеджер
@asynccontextmanager
async def async_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session