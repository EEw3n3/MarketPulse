import asyncio
from sqlmodel import select
from sqlalchemy.orm import selectinload
from app.core.database import async_session
from app.domain.models import Product, ProductGroup

async def debug_chains():
    async with async_session() as session:
        stmt = select(ProductGroup).options(selectinload(ProductGroup.products)).limit(50)
        groups = (await session.execute(stmt)).scalars().all()
        
        for g in groups:
            if len(g.products) < 1: continue
            
            print(f"\n📂 GROUP: {g.name}")
            for p in g.products:
                print(f"  ID: {p.id} | Store: {p.search_term} | Vol: {p.volume} | Price: {p.last_price} | Title: {p.title}")

if __name__ == "__main__":
    asyncio.run(debug_chains())
