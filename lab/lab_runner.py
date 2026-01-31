import asyncio
import sys
import os
from loguru import logger
from sqlmodel import SQLModel, create_engine, Session, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add project root to path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.domain.models import ScrapingRule, Product, PriceHistory
from app.services.scraper import scraper_service
from app.core.client import stealth_client

# --- LAB CONFIGURATION ---
LAB_DB_URL = "sqlite+aiosqlite:///lab/lab_test.db"
lab_engine = create_async_engine(LAB_DB_URL, echo=False)

async def init_lab_db():
    async with lab_engine.begin() as conn:
        # Create tables ONLY if they don't exist in the lab DB
        await conn.run_sync(SQLModel.metadata.create_all)
    logger.info("🧪 Lab Database Initialized.")

async def run_lab_test(site_url: str, limit: int = 50):
    """
    Runs an isolated test for a specific URL.
    """
    async_session = sessionmaker(lab_engine, class_=AsyncSession, expire_on_commit=False)
    
    await stealth_client.init_session()
    
    async with async_session() as session:
        logger.info(f"🧪 [LAB TEST] Starting validation for: {site_url}")
        
        # 1. We need to register the domain for rule generation
        from app.core.registry import register_domain
        register_domain(site_url)
        
        # 2. Get/Create rule using our AI generator
        from app.services.ai_generator import ai_generator
        # Fetch HTML using Tier 3 for complex sites
        from app.core.browser import browser_manager
        html = await browser_manager.get_page_content(site_url)
        if not html:
            logger.error("❌ Failed to fetch HTML in Lab mode.")
            return

        with open("lab_debug.html", "w", encoding="utf-8") as f:
            f.write(html)
        logger.info("📄 Lab debug HTML saved to lab_debug.html")

        rule = await ai_generator.get_or_create_rule(session, site_url, html)
        if not rule:
            logger.error("❌ AI failed to create a rule for this site.")
            return

        logger.info(f"🧬 [LAB] Testing Rule: {rule.site_name} | {rule.domain}")
        
        # 3. Execution
        items = await scraper_service.scrape_catalog(
            session=session,
            start_url=site_url,
            initial_html=html,
            max_items=limit,
            enable_price_filter=False # In lab, we want to see everything
        )
        
        # 4. Result Analysis
        if items:
            logger.success(f"✅ [LAB] Success! Collected {len(items)} items.")
            # Basic stats
            brands_found = [i.title for i in items if "Dior" in i.title or "Chanel" in i.title] # Just an example check
            logger.info(f"📊 Quality Check: Items with recognized patterns - {len(items)}")
        else:
            logger.error("❌ [LAB] Scraper returned 0 items.")

    from app.core.browser import browser_manager
    await browser_manager.stop()
    await stealth_client.close()

async def main():
    if not os.path.exists('lab'):
        os.makedirs('lab')
        
    await init_lab_db()
    
    # --- HERE YOU CAN SET THE TARGET ---
    target_url = "https://www.notino.lv/viriesu-smarzas/"
    
    print("\n" + "="*50)
    print(f"🧪 MARKETPULSE LABORATORY: {target_url}")
    print("="*50)
    
    await run_lab_test(target_url, limit=20)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
