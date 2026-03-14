import asyncio
import os
import sys
from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, selectinload

# Ensure the root project directory is in PYTHONPATH
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from app.domain.models import Product, ProductGroup
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)

async def debug_armani():
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        # Search for all products matching the name pattern
        stmt = select(Product).where(Product.title.like("%Stronger With You%")).options(selectinload(Product.group))
        products = (await session.execute(stmt)).scalars().all()
        
        print(f"--- PRODUCTS SEARCH: 'Stronger With You' ({len(products)} found) ---")
        for p in products:
            group_name = p.group.name if p.group else "None"
            price = p.last_price if p.last_price else 0.0
            print(f"ID: {p.id:4} | Group: {group_name:40} | Price: {price:>7.2f} € | Vol: {p.volume:8} | Title: {p.title}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(debug_armani())
