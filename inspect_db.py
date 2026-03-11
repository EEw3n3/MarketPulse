import asyncio
from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import sys
import os

# Ensure the root project directory is in PYTHONPATH so absolute imports work
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from app.domain.models import Product

# Connect to the main production database
MAIN_DB_URL = "sqlite+aiosqlite:///database.db"
engine = create_async_engine(MAIN_DB_URL, echo=False)

async def inspect():
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        # Check products, ordered by store name (search_term) and then ID
        stmt = select(Product).order_by(Product.search_term, Product.id.asc())
        products = (await session.execute(stmt)).scalars().all()
        
        print(f"\n📊 MARKET PULSE DATABASE: {len(products)} PRODUCTS FOUND")
        
        # ID | STORE | BRAND | TITLE | VOLUME | PRICE 
        print(f"{'ID':<4} | {'STORE':<12} | {'BRAND':<15} | {'TITLE':<50} | {'VOLUME':<8} | {'PRICE'}")
        print("-" * 115)
        
        for p in products:
            store_display = (p.search_term or "Unknown")[:12]
            brand_display = (p.brand or "Unknown")[:15]
            
            # Truncate title if it's too long to keep the table clean
            title_short = (p.title[:47] + '...') if len(p.title) > 50 else p.title
            
            vol_display = (p.volume or "---")[:8]
            price_display = f"{p.last_price:>7.2f} €" if p.last_price else "---"
            
            print(f"{p.id:<4} | {store_display:<12} | {brand_display:<15} | {title_short:<50} | {vol_display:<8} | {price_display}")
        
        print("-" * 115)
        print(f"✅ Inspection complete.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(inspect())
