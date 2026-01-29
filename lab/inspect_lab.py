import asyncio
import sys
import os
from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.domain.models import Product, PriceHistory

LAB_DB_URL = "sqlite+aiosqlite:///lab/lab_test.db"
engine = create_async_engine(LAB_DB_URL)

async def inspect_lab():
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        stmt = select(Product)
        results = await session.execute(stmt)
        products = results.scalars().all()
        
        print(f"\n🧪 [LAB INSPECT] Total: {len(products)} products")
        print(f"{'BRAND':<15} | {'VOL':<8} | {'CONC':<6} | {'PRICE':<8} | {'TITLE'}")
        print("-" * 100)
        
        for p in products:
            price = f"{p.last_price} €" if p.is_available else "NAV PIEEJAMS"
            print(f"{p.brand or 'N/A':<15} | {p.volume or 'N/A':<8} | {p.concentration or 'N/A':<6} | {price:<12} | {p.title}")
            
if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(inspect_lab())
