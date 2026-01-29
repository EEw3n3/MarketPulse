import asyncio
import time
import os
import sys
from decimal import Decimal

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.scraper import scraper_service
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Use LAB DB
LAB_DB_URL = "sqlite+aiosqlite:///lab/lab_test.db"
lab_engine = create_async_engine(LAB_DB_URL, echo=False)
async_session = sessionmaker(lab_engine, class_=AsyncSession, expire_on_commit=False)

async def run_benchmark():
    url = "https://makeup.lv/categorys/3218/"
    limit = 110 # About 3 pages
    
    print(f"🚀 Starting Turbo Benchmark: {url}")
    print(f"📦 Goal: Collect ~{limit} items in Turbo mode.")
    
    start_time = time.time()
    
    async with async_session() as session:
        items = await scraper_service.scrape_catalog(
            session=session,
            start_url=url,
            max_items=limit,
            site_name_ui="TurboTest"
        )
    
    end_time = time.time()
    duration = end_time - start_time
    
    print("\n" + "="*50)
    print("🏁 BENCHMARK RESULTS")
    print("="*50)
    print(f"Total items collected: {len(items)}")
    print(f"Total time: {duration:.2f} seconds")
    if len(items) > 0:
        print(f"Average speed: {duration/len(items):.2f} seconds per item")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(run_benchmark())
