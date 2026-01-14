import asyncio
import sys
from sqlmodel import select
from app.core.database import init_db, async_session
from app.domain.models import Product, PriceHistory

async def inspect_database():
    # Initialization (in case tables are not created, though they should be)
    await init_db()
    
    async with async_session() as session:
        # 1. Query all products
        statement = select(Product).order_by(Product.created_at.desc())
        results = await session.execute(statement)
        products = results.scalars().all()
        
        if not products:
            print("\n❌ Database empty. Start scraping first (main.py).")
            return

        print(f"\n📊 TOTAL IN DB: {len(products)} PRODUCTS")
        print(f"{'ID':<4} | {'STORE':<15} | {'PRICE':<10} | {'DATE':<19} | {'TITLE'}")
        print("-" * 100)
        
        for p in products:
            # 2. Get latest actual price for each product
            # (since history may contain many records)
            hist_stmt = select(PriceHistory).where(PriceHistory.product_id == p.id).order_by(PriceHistory.parsed_at.desc()).limit(1)
            hist_res = await session.execute(hist_stmt)
            latest_price_rec = hist_res.scalar_one_or_none()
            
            price_display = f"{latest_price_rec.price:>8.2f} €" if latest_price_rec else "---"
            date_display = latest_price_rec.parsed_at.strftime("%Y-%m-%d %H:%M:%S") if latest_price_rec else "---"
            title_short = (p.title[:50] + '...') if len(p.title) > 50 else p.title
            
            print(f"{p.id:<4} | {p.search_term:<15} | {price_display:<10} | {date_display:<19} | {title_short}")
        
        print("-" * 100)
        print(f"✅ Inspection finished. Total records: {len(products)}")

if __name__ == "__main__":
    # Windows/Docker specific event loop setting
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        asyncio.run(inspect_database())
    except KeyboardInterrupt:
        pass
