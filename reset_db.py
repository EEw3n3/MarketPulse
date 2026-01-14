import asyncio
import sys
import os

# Adding current directory to path to import app
sys.path.append(os.getcwd())

from app.core.database import engine
from sqlmodel import SQLModel
# Importing models to register them in metadata
from app.domain.models import Product, ProductGroup, ScrapingRule, PriceHistory, SharedPattern

async def reset_database():
    print("🗑️  Deleting old tables (Drop All)...")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    
    print("🏗️  Creating new tables (Create All)...")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    print("✅ Database successfully reloaded with new schema.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(reset_database())
