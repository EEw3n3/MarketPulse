import asyncio, sys, os
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.domain.models import Product

engine = create_async_engine(settings.DATABASE_URL, echo=False)

async def run():
    s = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with s() as session:
        # Check for duplicates (same URL + volume)
        from sqlalchemy import func
        r = await session.execute(
            select(Product.url, Product.volume, func.count(Product.id).label('cnt'))
            .group_by(Product.url, Product.volume)
            .having(func.count(Product.id) > 1)
        )
        dupes = r.all()
        print(f"=== DUPLICATE URL+VOLUME COMBOS: {len(dupes)} ===")
        for d in dupes[:10]:
            print(f"  url={d[0][:60]}... vol={d[1]} count={d[2]}")

        # Check products with missing critical fields
        r2 = await session.execute(
            select(Product).where(
                (Product.brand == None) | (Product.volume == None) | (Product.last_price == None)
            )
        )
        missing = r2.scalars().all()
        print(f"\n=== PRODUCTS WITH MISSING FIELDS: {len(missing)} ===")
        for p in missing[:15]:
            print(f"  ID={p.id} store={p.search_term} title='{p.title[:40]}' brand={p.brand} vol={p.volume} price={p.last_price}")
        
        # Show 220.lv sample data (not visible in terminal)
        r3 = await session.execute(
            select(Product).where(Product.search_term == '220.lv').order_by(Product.id).limit(10)
        )
        prods_220 = r3.scalars().all()
        print(f"\n=== 220.LV SAMPLE (first 10) ===")
        for p in prods_220:
            print(f"  ID={p.id} brand={p.brand} title='{p.title[:50]}' vol={p.volume} price={p.last_price}")

if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run())
