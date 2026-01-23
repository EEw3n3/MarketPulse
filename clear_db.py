import asyncio
from sqlmodel import delete
from app.core.database import init_db, async_session
from app.domain.models import Product, PriceHistory, ScrapingRule
from loguru import logger

async def clear_database():
    from app.domain.models import Product, PriceHistory, ProductGroup
    
    logger.warning("🗑️ Cleaning up dynamic data (Products, History, Groups)...")
    
    async with async_session() as session:
        # Delete only specific data models
        await session.execute(delete(PriceHistory))
        await session.execute(delete(Product))
        await session.execute(delete(ProductGroup))
        
        await session.commit()
        
    logger.success("✅ Dynamic data cleared. Scraping rules and patterns preserved!")


if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(clear_database())
