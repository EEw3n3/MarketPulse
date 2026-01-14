import asyncio
from sqlmodel import delete
from app.core.database import init_db, async_session
from app.domain.models import Product, PriceHistory, ScrapingRule
from loguru import logger

async def clear_database():
    from app.core.database import engine
    from sqlmodel import SQLModel
    
    logger.warning("🗑️ Complete database structure reset (DROP TABLES)...")
    
    async with engine.begin() as conn:
        # First drop all tables
        await conn.run_sync(SQLModel.metadata.drop_all)
        # Then recreate them with new columns
        await conn.run_sync(SQLModel.metadata.create_all)
        
    logger.success("✅ Database structure updated and cleaned!")


if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(clear_database())
