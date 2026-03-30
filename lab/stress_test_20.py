import asyncio
import sys
import os
import time
from loguru import logger
from sqlmodel import SQLModel, create_engine, Session, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add project root to path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.domain.models import ScrapingRule, Product, PriceHistory
from app.services.scraper import scraper_service
from app.core.client import stealth_client
from app.core.database import async_session_maker

# --- LAB CONFIGURATION ---
# We will use the production DB for this "Clean-Start" test run 
# but with restricted limits.
# Ensure you ran clear_db_data.py before this!

async def run_lab_test(site_url: str, label: str, limit: int = 20):
    """
    Runs a test run on the main database with a strict limit.
    """
    await stealth_client.init_session()
    
    async with async_session_maker() as session:
        t_start = time.time()
        logger.info(f"🧪 [STRESS TEST] Starting validation for {label}: {site_url}")
        
        # 1. Register domain
        from app.core.registry import register_domain
        register_domain(site_url)
        
        # 2. Get/Create rule using our AI generator
        from app.services.ai_generator import ai_generator
        from app.core.browser import browser_manager
        
        logger.info(f"🌐 Fetching {label} via browser...")
        response = await browser_manager.get_page_content(site_url)
        
        if not response or not response.get("html"):
            logger.error(f"❌ Failed to fetch HTML for {label}")
            return
            
        html = response["html"]

        rule = await ai_generator.get_or_create_rule(session, site_url, html)
        if not rule:
            logger.error(f"❌ AI failed to create a rule for {label}")
            return

        logger.info(f"🧬 [STRESS TEST] Rule for {label} is ready. Executing scrape...")
        
        # 3. Execution on PROD DB with LIMIT
        items = await scraper_service.scrape_catalog(
            session=session,
            start_url=site_url,
            initial_html=html,
            max_items=limit,
            enable_price_filter=False
        )
        
        # 4. Result Analysis
        if items:
            elapsed = time.time() - t_start
            logger.success(f"✅ [STRESS TEST] {label} Success! Collected {len(items)} items.")
            logger.info(f"⏱️  Time: {elapsed:.1f}s")
        else:
            logger.error(f"❌ [STRESS TEST] {label} returned 0 items.")

    from app.core.browser import browser_manager
    await browser_manager.stop()
    await stealth_client.close()

async def main():
    logger.info("🚀 Starting Multi-Site Stress Test (20 items per site)")
    
    test_sites = [
        {"url": "https://www.notino.lv/viriesu-smarzas/", "label": "Notino"},
        {"url": "https://www.douglas.lv/lv/katalogs/viriesu-parfimerija/", "label": "Douglas"},
        {"url": "https://makeup.lv/categorys/3/", "label": "Makeup.lv"},
        {"url": "https://www.1a.lv/c/smarzas-un-kosmetika/smarzas/viriesu-smarzas/2m2", "label": "1a.lv"},
        {"url": "https://220.lv/lv/smarzas/viriesu-smarzas", "label": "220.lv"},
    ]
    
    for site in test_sites:
        try:
            await run_lab_test(site["url"], site["label"], limit=20)
            # Small cooldown between domains to be stealthy
            await asyncio.sleep(5) 
        except Exception as e:
            logger.exception(f"💥 Critical failure on {site['label']}: {e}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
