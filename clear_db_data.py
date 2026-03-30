import asyncio
from sqlmodel import delete
from app.core.database import async_session_maker
from app.domain.models import Product, ProductGroup, PriceHistory

async def clear_data():
    print("🚀 Starting Database Data Wipe...")
    async with async_session_maker() as session:
        try:
            # Order is important due to foreign keys
            print("🗑️ Deleting Price History...")
            await session.execute(delete(PriceHistory))
            
            print("🗑️ Deleting Products...")
            await session.execute(delete(Product))
            
            print("🗑️ Deleting Product Groups (Chains)...")
            await session.execute(delete(ProductGroup))
            
            await session.commit()
            print("✅ Database data cleared successfully! (Rules and Patterns preserved)")
        except Exception as e:
            await session.rollback()
            print(f"❌ Error during wipe: {e}")

if __name__ == "__main__":
    asyncio.run(clear_data())
