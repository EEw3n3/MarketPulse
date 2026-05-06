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

from app.core.config import settings
from app.services.intent import intent_service

def clean_text(text: str) -> str:
    """Removes potential surrogate characters and non-utf8 garbage from terminal input."""
    return text.encode('utf-8', 'ignore').decode('utf-8').strip()


# TARGET_COUNT relocated to settings.DEFAULT_TARGET_COUNT

async def get_hybrid_html(url: str, force_browser: bool = False) -> str | None:
    """
    Attempts to fetch HTML content using a tiered approach:
    Tier 1: Fast stealth client
    Tier 3: Full browser rendering (if Tier 1 fails or if forced).
    """
    if force_browser:
        logger.warning(f"🚜 [Tier 3] Forced browser launch for {url}...")
        try:
            resp = await browser_manager.get_page_content(url)
            html = resp["html"] if resp else None
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

async def process_target(session, target: dict, intent: dict | None, group_id: int | None, enable_price_filter: bool = True, max_items: int | None = None):
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
    site_name_ui = target.get("site_name")
    effective_max = max_items if max_items is not None else settings.DEFAULT_TARGET_COUNT

    products = await scraper_service.scrape_catalog(
        session, url, html, max_items=effective_max, group_id=group_id, intent=intent,
        enable_price_filter=enable_price_filter, site_name_ui=site_name_ui
    )

    scraper_service.validate_dataset(products)

# Semaphore for limiting concurrent tasks
scrape_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_SCRAPES)

async def process_target_worker(target: dict, intent: dict | None, group_id: int | None, enable_price_filter: bool = True, max_items: int | None = None):
    async with scrape_semaphore:
        async with async_session() as session:
            try: await process_target(session, target, intent, group_id, enable_price_filter, max_items=max_items)
            except Exception as e: logger.exception(f"💥 Error {target['url']}: {e}")

async def main():
    
    BANNER = rf"""
    ___  ___           _        _  ______      _             
    |  \/  |          | |      | | | ___ \    | |            
    | .  . | __ _ _ __| | _____| |_| |_/ /   _| |___  ___    
    | |\/| |/ _` | '__| |/ / _ \ __|  __/ | | | / __|/ _ \   
    | |  | | (_| | |  |   <  __/ |_| |  | |_| | \__ \  __/   
    \_|  |_/\__,_|_|  |_|\_\___|\__\_|   \__,_|_|___/\___|   
                                           v{settings.VERSION}
    """
    
    print(BANNER)
    logger.info(f"🚀 Launching {settings.PROJECT_NAME}: Intelligence CLI")
    
    print("\n" + "="*50)
    print(f"🤖 WELCOME TO {settings.PROJECT_NAME.upper()} CLI")
    print("="*50)
    print("Choose operation mode:")
    print("1. 🎯 Smart Search (Interactive Search)")
    print("2. 🚜 Mass Scraping (Category Training / Mass Scrape)")
    print("3. ☠️  HARDCORE MODE (Full Market Monitor - Auto Match)")
    print("4. 🕰️  AUTO MODE (24/7 Scheduled Scrape)")
    print("-" * 50)
    
    choice = input("👉 Select option (1, 2, 3, or 4): ").strip()
    
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

            # Load search targets from config — same source as Hardcore Mode.
            # Each store can define an optional "search_url_template" with a {query} placeholder.
            # If absent, the base catalog URL is used (AI will apply intent filtering instead).
            import json as _json
            try:
                with open("configs/categories.json", "r", encoding="utf-8") as _f:
                    _cats = _json.load(_f)
                _store_targets = _cats.get("mens_perfume", {}).get("targets", [])
            except Exception as _e:
                logger.error(f"❌ Could not load configs/categories.json: {_e}")
                _store_targets = []

            dynamic_targets = []
            for _t in _store_targets:
                # If store has a search template, build a search URL; otherwise use catalog URL
                _tmpl = _t.get("search_url_template")
                _url = _tmpl.format(query=encoded_query) if _tmpl else _t["url"]
                dynamic_targets.append({
                    "url": _url,
                    "search_term": search_term,
                    "category": _t.get("category", category),
                    "site_name": _t.get("site", "Unknown"),
                })

            if not dynamic_targets:
                logger.error("❌ No store targets configured in configs/categories.json!")
                return

            from app.core.registry import register_domain
            for t in dynamic_targets: register_domain(t["url"])

            logger.info(f"🔎 Smart Search across {len(dynamic_targets)} stores: {[t['site_name'] for t in dynamic_targets]}")

            # Launch parallel parsing and pass group_id
            tasks = [asyncio.create_task(process_target_worker(target, intent, group_id, enable_price_filter=True)) for target in dynamic_targets]
            await asyncio.gather(*tasks)


        elif choice == "2":
            # --- MODE 2: MASS SCRAPING ---
            print("\n🚜 TRAINING MODE (Mass Scrape)")
            target_url = clean_text(input("🔗 Enter catalog/category URL: "))
            search_term = clean_text(input("🏷️ Name this group (e.g., Nike Shoes): "))
            category = clean_text(input("📁 Category (Electronics/Shoes/etc): ")) or "General"
            limit_input = clean_text(input("🔢 Item limit (default 10): "))
            limit = int(limit_input) if limit_input.isdigit() else 10
            
            # Items limit logic
            # global TARGET_COUNT -> now handled via settings instance if needed, 
            # but we use local 'limit' for this specific run

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
            # Remove default stdout logger to avoid corrupting rich UI
            import sys
            logger.remove()
            logger.add("hardcore_monitor.log", rotation="5 MB")
            
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
            from app.services.ui import init_dashboard
            from urllib.parse import urlparse
            
            site_names = [t.get("site", urlparse(t["url"]).netloc) for t in targets]
            db = init_dashboard(site_names)
            
            tasks = []
            logger.info(f"🚀 Loaded {len(targets)} data sources. Initializing Dashboard...")
            
            from rich.live import Live
            with Live(db.generate_layout(), refresh_per_second=4, screen=True) as live:
                for t in targets:
                    site_name = t.get("site", "Unknown")
                    register_domain(t["url"])
                    target_payload = {
                        "url": t["url"],
                        "search_term": "HardcoreMonitor", 
                        "category": t["category"],
                        "site_name": site_name # Pass site name for UI
                    }
                    tasks.append(asyncio.create_task(process_target_worker(target_payload, None, None)))
                
                # Update loop for Live display
                while not all(task.done() for task in tasks if tasks):
                    live.update(db.generate_layout())
                    await asyncio.sleep(0.5)
                
                await asyncio.gather(*tasks)

        elif choice == "4":
            # --- MODE 4: AUTO MODE (24/7 SCHEDULER) ---
            logger.remove()
            logger.add("scheduler.log", rotation="5 MB")
            logger.info("🕰️ Starting Auto Mode...")
            
            from app.services.scheduler import scheduler_service
            scheduler_service.start(interval_hours=12) # For example, every 12 hours
            
            # Keep event loop running forever
            try:
                while True:
                    await asyncio.sleep(3600)
            except asyncio.CancelledError:
                scheduler_service.stop()
                raise
        
        else:
            logger.error("Invalid mode selection.")
            return

        if choice == "4":
            return # Scheduler mode doesn't need to run the final analysis once

        # 5. FINAL ANALYSIS (only for search mode, or if data exists)
        logger.info("\n📊 GROUP REPORT GENERATION...")
        from app.services.analyzer import price_analyzer
        from app.domain.models import ProductGroup

        from sqlalchemy.orm import selectinload
        async with async_session() as session:
            # Fetch a larger pool of recent groups to find the best chains
            groups_stmt = select(ProductGroup).options(selectinload(ProductGroup.products)).order_by(ProductGroup.created_at.desc()).limit(200)
            results = await session.execute(groups_stmt)
            groups = results.scalars().all()

            # First, analyze all recently created groups
            all_analyses = []
            for g in groups:
                analysis = await price_analyzer.analyze_group(session, g.id)
                if analysis:
                    all_analyses.append(analysis)

            # Sort groups by the new 'score' metric (max items in a single volume bucket)
            sorted_analyses = sorted(all_analyses, key=lambda a: a.get("score", 0), reverse=True)[:15]

            for analysis in sorted_analyses:
                print(f"\n💎 REPORT: {analysis['name']}")
                print(f"   Category:   {analysis['category']}")
                print(f"   Volumes:")
                
                # Sort volumes alphabetically (or by size if possible, string sort is fine for now)
                for vol, stats in sorted(analysis["volumes"].items()):
                    print(f"     - {vol}:")
                    print(f"          Count: {stats['count']} items")
                    print(f"          Avg:   {float(stats['avg_price']):.2f} €")
                    print(f"          Best:  {float(stats['best_price']):.2f} € ({stats['best_store']})")
                print(f"{'—' * 60}")

    finally:
        await stealth_client.close()
        await browser_manager.stop()
        # Give Windows ProactorEventLoop time to cleanly close Playwright pipes
        await asyncio.sleep(0.5)

if __name__ == "__main__":
    if sys.platform == 'win32':
        # Playwright and other subprocess-based async tasks require ProactorEventLoop on Windows
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
