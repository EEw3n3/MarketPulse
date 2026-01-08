import asyncio
import sys
import os

# Добавляем текущую директорию в путь, чтобы можно было импортировать app
sys.path.append(os.getcwd())

from app.core.database import engine
from sqlmodel import SQLModel
# Импортируем модели, чтобы они зарегистрировались в метаданных
from app.domain.models import Product, ProductGroup, ScrapingRule, PriceHistory, SharedPattern

async def reset_database():
    print("🗑️  Удаление старых таблиц (Drop All)...")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    
    print("🏗️  Создание новых таблиц (Create All)...")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    print("✅ База данных успешно перезагружена с новой схемой.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(reset_database())
