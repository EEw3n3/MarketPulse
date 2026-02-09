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
        stmt = select(Product).options(selectinload(Product.history)).order_by(Product.id.desc()).limit(20)
        products = (await session.execute(stmt)).scalars().all()
        
        print(f"\n📊 LAB RESULTS: {len(products)} PRODUCTS FOUND")
        print(f"{'ID':<4} | {'BRAND/SHOP':<15} | {'PRICE':<10} | {'DATE':<19} | {'TITLE'}")
        print("-" * 110)
        
        for p in products:
            latest_price_rec = p.history[-1] if p.history else None
            price_display = f"{latest_price_rec.price:>8.2f} €" if latest_price_rec else "---"
            date_display = latest_price_rec.parsed_at.strftime("%Y-%m-%d %H:%M:%S") if latest_price_rec else "---"
            title_short = (p.title[:50] + '...') if len(p.title) > 50 else p.title
            
            # Using brand as 'STORE' equivalent for lab context
            shop_display = (p.brand or "Unknown")[:15]
            
            print(f"{p.id:<4} | {shop_display:<15} | {price_display:<10} | {date_display:<19} | {title_short}")
        
        print("-" * 110)
        print(f"✅ Lab inspection finished.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(inspect())
