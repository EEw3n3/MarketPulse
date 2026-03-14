import asyncio
import os
import sys
from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Ensure the root project directory is in PYTHONPATH
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from app.domain.models import Product, ScrapingRule
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)

async def check_douglas():
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        # Just get all products and filter in Python to be safe from SQL dialect issues
        stmt = select(Product)
        products = (await session.execute(stmt)).scalars().all()
        
        douglas_prods = [p for p in products if p.search_term and "douglas" in p.search_term.lower()]
        
        print(f"--- DOUGLAS DATA CHECK ({len(douglas_prods)} products found) ---")
        for p in douglas_prods[:30]:
            print(f"ID: {p.id:4} | Price: {p.last_price:>7.2f} € | Vol: {p.volume:8} | Title: {p.title}")
            print(f"     URL: {p.url}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(check_douglas())
