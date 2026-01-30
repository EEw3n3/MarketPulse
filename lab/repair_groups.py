import asyncio
import os
import sys
from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from loguru import logger

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.domain.models import Product, ProductGroup
from app.services.matcher import matcher_service
from app.services.normalizer import perfume_normalizer

DB_PATH = "sqlite+aiosqlite:///lab/lab_test.db"
engine = create_async_engine(DB_PATH, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def repair_database():
    logger.info("🚀 FAST O(N) RE-GROUPING...")
    
    async with async_session() as session:
        # 1. Cleanup
        await session.execute(delete(ProductGroup))
        await session.execute(update(Product).values(group_id=None))
        await session.commit()
        logger.info("🧹 Database wiped.")

        # 2. Fetch all products
        stmt = select(Product)
        result = await session.execute(stmt)
        products = result.scalars().all()
        logger.info(f"📦 Processing {len(products)} products...")

        # 3. One-pass grouping
        # canonical_name -> ProductGroup object
        groups_cache = {}
        
        reassigned = 0
        
        for p in products:
            # get_canonical_name returns "Brand CleanName Concentration"
            # It's unique enough for a scent chain
            c_name = matcher_service.get_canonical_name(p.title)
            
            # Additional safety: don't let empty/garbage names cluster
            # matcher_service.get_canonical_name already handles this by returning full title if clean fails
            
            if c_name not in groups_cache:
                new_group = ProductGroup(name=c_name, category="Perfume")
                session.add(new_group)
                await session.flush()
                groups_cache[c_name] = new_group
            
            target_group = groups_cache[c_name]
            p.group_id = target_group.id
            session.add(p)
            reassigned += 1
            
            if reassigned % 500 == 0:
                logger.info(f"🔄 Processed {reassigned} products...")
        
        await session.commit()
        logger.success(f"✅ Fast re-grouping complete! {len(groups_cache)} unique chains created for {reassigned} products.")

async def main():
    if not os.path.exists("lab/lab_test.db"):
        logger.error("Database not found!")
        return
    await repair_database()

if __name__ == "__main__":
    asyncio.run(main())
