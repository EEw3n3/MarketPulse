import asyncio
import sys
from urllib.parse import quote_plus
from loguru import logger
from sqlmodel import select

from app.core.database import init_db, async_session
from app.core.client import stealth_client
from app.core.browser import browser_manager
from app.services.ai_generator import ai_generator
from app.services.scraper import scraper_service
from app.core.registry import register_domain
# No longer using hardcoded TARGETS
# TARGETS = [...] 
from app.services.intent import intent_service


TARGET_COUNT = 20 

async def get_hybrid_html(url: str, force_browser: bool = False) -> str | None:
    """
    Attempts to fetch HTML content using a tiered approach:
    Tier 1: Fast stealth client
    Tier 3: Full browser rendering (if Tier 1 fails or if forced).
    """
    if force_browser:
        logger.warning(f"🚜 [Tier 3] Forced browser launch for {url}...")
        try:
            html = await browser_manager.get_page_content(url)
            if html and len(html) > 1000:
                logger.success(f"✅ [Tier 3] Browser rendered the page! ({len(html)} bytes)")
                return html
        except Exception as e:
            logger.critical(f"❌ [Tier 3] Browser error: {e}")
        return None

    logger.info(f"⚡ [Tier 1] Trying fast method for {url}...")
    try:
        html = await stealth_client.get_page(url)
        if html and len(html) > 1000 and "Access Denied" not in html:
            logger.success(f"✅ [Tier 1] Success! Received {len(html)} bytes.")
            return html
        else:
            logger.warning("⚠️ [Tier 1] Unsuccessful (block or empty response).")
    except Exception as e:
        logger.error(f"⚠️ [Tier 1] Error: {e}")

    return await get_hybrid_html(url, force_browser=True)

from app.services.validator import content_validator

async def process_target(session, target: dict, intent: dict, group_id: int, enable_price_filter: bool = True):
    url = target["url"]
    search_term = target["search_term"]

    logger.info(f"\n🏁 STARTING CHECK: {url}")
    
    html = await get_hybrid_html(url)
    if not html: return

    rule = await ai_generator.get_or_create_rule(session, url, html)
    if not rule:
        logger.warning("🤔 Rule not created. Trying Browser...")
        html = await get_hybrid_html(url, force_browser=True)
        rule = await ai_generator.get_or_create_rule(session, url, html)
        
    if not rule:
        logger.error("❌ Failed to create rule.")
        return

    logger.info(f"📦 [{rule.site_name}] Attempting collection...")
    products = await scraper_service.scrape_catalog(
        session, url, html, max_items=TARGET_COUNT, group_id=group_id, intent=intent, enable_price_filter=enable_price_filter
    )
    
    # --- Filtering now happens inside scrape_catalog ---
    # if intent and products:
    #     content_validator.validate_items(products, intent)
    
    # Validation report remains for rule health metrics
    scraper_service.validate_dataset(products)

# Semaphore for limiting concurrent tasks
MAX_CONCURRENT_SCRAPES = 3
scrape_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SCRAPES)

async def process_target_worker(target: dict, intent: dict, group_id: int, enable_price_filter: bool = True):
    async with scrape_semaphore:
        async with async_session() as session:
            try: await process_target(session, target, intent, group_id, enable_price_filter)
            except Exception as e: logger.error(f"💥 Error {target['url']}: {e}")

async def main():
    logger.info("🚀 Launching MarketPulse: Intelligence CLI")
    
    print("\n" + "="*50)
    print("🤖 WELCOME TO MARKETPULSE CLI")
    print("="*50)
    print("Choose operation mode:")
    print("1. 🎯 Smart Search (Interactive Search)")
    print("2. 🚜 Mass Scraping (Category Training / Mass Scrape)")
    print("3. ☠️  HARDCORE MODE (Full Market Monitor - Auto Match)")
    print("-" * 50)
    
    choice = input("👉 Select option (1 or 2): ").strip()
    
    await init_db()
    await stealth_client.init_session()

    try:
        if choice == "1":
            # --- MODE 1: SMART SEARCH ---
            user_query = input("\n🎯 What are we looking for? (e.g., iPhone 16): ").strip()
            if not user_query: return
            
            intent = await intent_service.parse_user_query(user_query)
            search_term = intent["search_term"]
            category = intent["category"]
            
            # --- CENTRALIZED GROUP CREATION ---
            from app.domain.models import ProductGroup
            async with async_session() as session:
                stmt = select(ProductGroup).where(ProductGroup.name == search_term)
                # Use .first() to avoid crashing if duplicate exists
                group = (await session.execute(stmt)).scalars().first()
                if not group:
                    group = ProductGroup(name=search_term, category=category)
                    session.add(group)
                    await session.commit()
                    await session.refresh(group)
                    logger.info(f"📁 New group created: {search_term}")
                group_id = group.id

            encoded_query = quote_plus(search_term)
            dynamic_targets = [
                {
                    "url": f"https://www.rdveikals.lv/search/lv/word/{encoded_query}/page/1/",
                    "search_term": search_term,
                    "category": category
                },
                {
                     "url": f"https://www.nike.com/w?q={encoded_query}",
                     "search_term": search_term,
                     "category": category
                }
            ]
            
            from app.core.registry import register_domain
            for t in dynamic_targets: register_domain(t["url"])

            # 4. Launch parallel parsing and pass group_id
            tasks = [process_target_worker(target, intent, group_id, enable_price_filter=True) for target in dynamic_targets]
            await asyncio.gather(*tasks)

        elif choice == "2":
            # --- MODE 2: MASS SCRAPING ---
            print("\n🚜 TRAINING MODE (Mass Scrape)")
            target_url = input("🔗 Enter catalog/category URL: ").strip()
            search_term = input("🏷️ Name this group (e.g., Nike Shoes): ").strip()
            category = input("📁 Category (Electronics/Shoes/etc): ").strip() or "General"
            limit = input("🔢 Item limit (default 10): ").strip()
            limit = int(limit) if limit.isdigit() else 10
            
            global TARGET_COUNT
            TARGET_COUNT = limit

            # Creating group for mode 2
            from app.domain.models import ProductGroup
            async with async_session() as session:
                stmt = select(ProductGroup).where(ProductGroup.name == search_term)
                group = (await session.execute(stmt)).scalars().first()
                if not group:
                    group = ProductGroup(name=search_term, category=category)
                    session.add(group)
                    await session.commit()
                    await session.refresh(group)
                group_id = group.id

            from app.core.registry import register_domain
            register_domain(target_url)

            target = {
                "url": target_url,
                "search_term": search_term,
                "category": category
            }
            
            await process_target_worker(target, None, group_id, enable_price_filter=False)

        elif choice == "3":
            # --- MODE 3: HARDCORE MONITOR ---
            logger.warning("☠️  STARTING HARDCORE MARKET MONITOR")
            logger.info("Subject: Men's Perfume (Vīriešu smaržas)")
            
            import json
            try:
                with open("configs/categories.json", "r", encoding="utf-8") as f:
                    cats = json.load(f)
                    targets = cats.get("mens_perfume", {}).get("targets", [])
            except Exception as e:
                logger.error(f"❌ Config error: {e}")
                return

            if not targets:
                logger.error("❌ No targets found in config!")
                return

            from app.core.registry import register_domain
            
            tasks = []
            logger.info(f"🚀 Loaded {len(targets)} data sources.")
            
            for t in targets:
                register_domain(t["url"])
                target_payload = {
                    "url": t["url"],
                    "search_term": "HardcoreMonitor", 
                    "category": t["category"]
                }
                # group_id=None signals the scraper to use MatcherService
                tasks.append(process_target_worker(target_payload, None, None))
            
            await asyncio.gather(*tasks)
        
        else:
            logger.error("Invalid mode selection.")
            return

        # 5. FINAL ANALYSIS (only for search mode, or if data exists)
        logger.info("\n📊 GROUP REPORT GENERATION...")
        from app.services.analyzer import price_analyzer
        from app.domain.models import ProductGroup

        from sqlalchemy.orm import selectinload
        async with async_session() as session:
            # Added selectinload option so products load immediately (fix MissingGreenlet)
            groups_stmt = select(ProductGroup).options(selectinload(ProductGroup.products)).order_by(ProductGroup.created_at.desc()).limit(1)
            results = await session.execute(groups_stmt)
            groups = results.scalars().all()

            for g in groups:
                analysis = await price_analyzer.analyze_group(session, g.id)
                if analysis:
                    print(f"\n💎 REPORT: {g.name}")
                    print(f"   Category:   {g.category}")
                    print(f"   Count:      {len(g.products)} items")
                    print(f"   Avg. price: {analysis['avg_group_price']} €")
                    print(f"   Best:       {analysis['best_price']} € ({analysis['best_store']})")
                    print(f"{'—' * 60}")

    finally:
        await stealth_client.close()
        await browser_manager.stop()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
