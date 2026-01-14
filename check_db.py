import asyncio
from sqlmodel import select
from sqlalchemy.orm import selectinload
from app.core.database import async_session
from app.domain.models import Product

async def check():
    async with async_session() as session:
        # Loading products with their history (selectinload)
        statement = select(Product).options(selectinload(Product.history))
        result = await session.execute(statement)
        products = result.scalars().all()
        
        print(f"\n--- DATABASE REPORT ---")
        print(f"Total products in DB: {len(products)}")
        
        for p in products[:3]: # Showing first 3 products
            print(f"\n📦 Product: {p.title}")
            print(f"🔗 URL: {p.url}")
            print(f"📊 Price history records: {len(p.history)}")
            for h in p.history:
                print(f"   🕒 {h.parsed_at.strftime('%H:%M:%S')} -> {h.price} RUB")

if __name__ == "__main__":
    asyncio.run(check())