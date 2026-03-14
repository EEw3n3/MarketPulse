import asyncio
import os
import sys
from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

# Ensure the root project directory is in PYTHONPATH
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from app.domain.models import Product, ScrapingRule
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)

async def check():
    async with AsyncSession(engine) as session:
        # Check Rules
        rules = (await session.execute(select(ScrapingRule))).scalars().all()
        print("--- RULES ---")
        for r in rules:
            print(f"Domain: {r.domain} | Site: {r.site_name}")
            
        # Check Products for Douglas
        stmt = select(Product).where(Product.url.like("%douglas.lv%")).limit(10)
        douglas_prods = (await session.execute(stmt)).scalars().all()
        print("\n--- DOUGLAS PRODUCTS ---")
        for p in douglas_prods:
            print(f"ID: {p.id} | Store (SearchTerm): {p.search_term} | Price: {p.last_price} | URL: {p.url}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(check())
