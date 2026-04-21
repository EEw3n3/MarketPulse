"""
Seed production Postgres DB with a small scrape for Phase 2 verification.

Run INSIDE the docker-compose app container:
  docker-compose exec app python scripts/seed_prod_db.py

Or locally (requires DATABASE_URL in .env pointing to localhost:5432):
  python scripts/seed_prod_db.py

Scrapes 2 sites x 20 items → enough to verify all 4 API endpoints.
"""
import asyncio
import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from loguru import logger
from app.core.database import async_session_maker, init_db
from app.core.registry import register_domain
from app.core.browser import browser_manager
from app.services.ai_generator import ai_generator
from app.services.scraper import scraper_service

SEED_SITES = [
    {
        "url": "https://www.notino.lv/viriesu-smarzas/",
        "label": "notino.lv",
        "limit": 20,
    },
    {
        "url": "https://220.lv/lv/smarzas/viriesu_smarzas",
        "label": "220.lv",
        "limit": 20,
    },
]


async def seed_site(url: str, label: str, limit: int) -> dict:
    t0 = time.time()
    logger.info(f"🌱 Seeding {label} (limit={limit}) ...")
    try:
        register_domain(url)
        resp = await browser_manager.get_page_content(url)
        if not resp or not resp.get("html"):
            return {"label": label, "ok": False, "error": "Failed to fetch HTML"}
        html = resp["html"]

        async with async_session_maker() as session:
            rule = await ai_generator.get_or_create_rule(session, url, html)
            if not rule:
                return {"label": label, "ok": False, "error": "AI failed to create rule"}

            items = await scraper_service.scrape_catalog(
                session=session,
                start_url=url,
                initial_html=html,
                max_items=limit,
                enable_price_filter=False,
            )

        elapsed = round(time.time() - t0, 1)
        logger.success(f"✅ {label}: {len(items)} items in {elapsed}s")
        return {"label": label, "ok": True, "count": len(items), "elapsed": elapsed}
    except Exception as e:
        logger.exception(f"❌ {label}: {e}")
        return {"label": label, "ok": False, "error": str(e)}


async def main():
    logger.info("🗄️  Initializing prod DB tables (if any missing)...")
    await init_db()

    results = []
    for site in SEED_SITES:
        r = await seed_site(site["url"], site["label"], site["limit"])
        results.append(r)

    print("\n--- Seed Results ---")
    for r in results:
        if r["ok"]:
            print(f"  ✅ {r['label']}: {r['count']} items ({r['elapsed']}s)")
        else:
            print(f"  ❌ {r['label']}: {r['error']}")
    print("--------------------")

    await browser_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
