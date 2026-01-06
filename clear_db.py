import asyncio
from sqlmodel import delete
from app.core.database import init_db, async_session
from app.domain.models import Product, PriceHistory, ScrapingRule
from loguru import logger

async def clear_database():
    from app.core.database import engine
    from sqlmodel import SQLModel
    
    logger.warning("🗑️ Полный сброс структуры базы данных (DROP TABLES)...")
    
    async with engine.begin() as conn:
        # Сначала удаляем все таблицы
        await conn.run_sync(SQLModel.metadata.drop_all)
        # Затем создаем их заново с новыми колонками
        await conn.run_sync(SQLModel.metadata.create_all)
        
    logger.success("✅ Структура базы данных обновлена и очищена!")


if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(clear_database())
