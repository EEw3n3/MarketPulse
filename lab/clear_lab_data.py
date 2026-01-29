import asyncio
import os
import sys
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

LAB_DB_URL = "sqlite+aiosqlite:///lab/lab_test.db"
engine = create_async_engine(LAB_DB_URL)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def clear_lab_data():
    """
    Deletes all products and prices from the lab database, 
    but PRESERVES ScrapingRules (selectors).
    """
    if not os.path.exists("lab/lab_test.db"):
        logger.error("❌ Lab database not found.")
        return

    async with async_session() as session:
        async with session.begin():
            # Delete in order to respect potential foreign keys (though SQLite is loose)
            await session.execute(text("DELETE FROM pricehistory"))
            await session.execute(text("DELETE FROM product"))
            # We also clear product groups as they are linked to products
            await session.execute(text("DELETE FROM productgroup"))
            
            logger.warning("🧹 Lab database cleared: Products, Groups, and History DELETED.")
            logger.success("💾 KEEPING ScrapingRules (Selectors) intact.")
            
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(clear_lab_data())
