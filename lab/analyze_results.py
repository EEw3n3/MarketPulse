import asyncio
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import sys
import os
from decimal import Decimal

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.domain.models import Product

# Use LAB DB URL
LAB_DB_URL = "sqlite+aiosqlite:///lab/lab_test.db"
lab_engine = create_async_engine(LAB_DB_URL, echo=False)

async def analyze_data():
    async_session = sessionmaker(lab_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        # Total count
        total = (await session.execute(select(func.count(Product.id)))).scalar()
        
        # Unique brands
        brands_res = await session.execute(select(Product.brand, func.count(Product.id)).group_by(Product.brand).order_by(func.count(Product.id).desc()).limit(15))
        top_brands = brands_res.all()
        
        # Price range
        prices = await session.execute(select(func.min(Product.last_price), func.max(Product.last_price), func.avg(Product.last_price)))
        min_p, max_p, avg_p = prices.one()
        
        # Check for empty brands or titles
        empty_brands = (await session.execute(select(func.count(Product.id)).where(Product.brand == None))).scalar()
        
        print("\n" + "="*50)
        print("📊 MAKEUP.LV DATA ANALYSIS")
        print("="*50)
        print(f"Total products scraped: {total}")
        print(f"Price range: {min_p}€ - {max_p}€ (Avg: {avg_p:.2f}€)")
        print(f"Products with missing brand: {empty_brands}")
        print("\nTOP 15 BRANDS:")
        for brand, count in top_brands:
            print(f"- {brand or 'Unknown'}: {count} items")
        print("="*50)

if __name__ == "__main__":
    asyncio.run(analyze_data())
