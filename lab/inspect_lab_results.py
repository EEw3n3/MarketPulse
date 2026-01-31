import asyncio
from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, selectinload
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.domain.models import ScrapingRule, Product, PriceHistory

LAB_DB_URL = "sqlite+aiosqlite:///lab/lab_test.db"
lab_engine = create_async_engine(LAB_DB_URL, echo=False)

async def inspect():
    async_session = sessionmaker(lab_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        # Check rule
        stmt = select(ScrapingRule).where(ScrapingRule.domain == "notino.lv")
        result = await session.execute(stmt)
        rule = result.scalar_one_or_none()
        
        if rule:
            print(f"--- RULE for {rule.domain} ---")
            print(f"Container CSS: {rule.container_css}")
            print(f"Title CSS:     {rule.title_css}")
            print(f"Price CSS:     {rule.price_css}")
            print(f"Image CSS:     {rule.image_css}")
            print(f"Next Page:     {rule.next_page_css}")
        else:
            print("No rule found for notino.lv.")

        # Check products
        stmt = select(Product).options(selectinload(Product.price_history)).limit(5)
        products = (await session.execute(stmt)).scalars().all()
        
        print(f"\n--- PRODUCTS SAMPLE ({len(products)}) ---")
        for p in products:
            latest_price = p.price_history[-1].price if p.price_history else 0
            print(f"[{p.id}] {p.title[:50]}... | Price: {latest_price} | Hash: {p.url_hash[:10]}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(inspect())
