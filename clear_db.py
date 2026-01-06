import asyncio
from sqlmodel import delete
from app.core.database import init_db, async_session
from app.domain.models import Product, PriceHistory, ScrapingRule
from loguru import logger

async def clear_database():
    await init_db()
    async with async_session() as session:
        logger.warning("🗑️ Начинаю полную очистку базы данных...")
        
        # Удаляем в правильном порядке из-за внешних ключей
        await session.execute(delete(PriceHistory))
        await session.execute(delete(Product))
        await session.execute(delete(ScrapingRule))
        
        await session.commit()
        logger.success("✅ База данных полностью очищена!")

if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(clear_database())
