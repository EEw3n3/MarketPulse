"""
Seed production Postgres DB with a real scrape via the main app DB engine.

Unlike `lab/lab_runner.py` (which writes to a local SQLite file at
`lab/lab_test.db`), this script uses `app.core.database.async_session_maker`,
which honours `DATABASE_URL` from your `.env` — so pointing it at the prod
Postgres writes data straight into production.

Usage:
  # Full scrape of all 5 sites into the DB pointed at by DATABASE_URL
  python scripts/seed_prod_db.py --full

  # One site only
  python scripts/seed_prod_db.py --site notino

  # Custom per-site limit
  python scripts/seed_prod_db.py --limit 50

DATABASE_URL must point at the target DB before running. To write into prod:
  DATABASE_URL=postgresql+asyncpg://market_user:market_password@46.101.174.12:5432/market_pulse_db
"""
import argparse
import asyncio
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from loguru import logger

from app.core.browser import browser_manager
from app.core.database import async_session_maker, init_db
from app.core.registry import register_domain
from app.services.ai_generator import ai_generator
from app.services.scraper import scraper_service

SITES = {
    "douglas": "https://www.douglas.lv/lv/katalogs/smarzas/viriesu-smarzas/smarzas/",
    "notino": "https://www.notino.lv/viriesu-smarzas/",
    "makeup": "https://makeup.lv/categorys/3218/",
    "220": "https://220.lv/lv/smarzas/viriesu_smarzas",
    "1a": "https://www.1a.lv/c/smarzas-un-kosmetika/viriesu-smarzas/viriesu-smarzas/30j",
}


async def seed_site(label: str, url: str, limit: int) -> dict:
    t0 = time.time()
    logger.info(f"🌱 Seeding {label} (limit={limit}) — {url}")
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


async def main(sites: list[str], limit: int) -> None:
    from app.core.config import settings
    db_target = settings.DATABASE_URL
    if "@localhost" in db_target or "@127.0.0.1" in db_target:
        logger.warning(f"DATABASE_URL points at LOCAL DB: {db_target}")
    else:
        logger.info(f"DATABASE_URL → {db_target}")

    logger.info("🗄️  Ensuring prod DB tables exist (no-op if already migrated)...")
    await init_db()

    results = []
    for label in sites:
        url = SITES[label]
        r = await seed_site(label, url, limit)
        results.append(r)

    print("\n--- Seed Results ---")
    total = 0
    for r in results:
        if r["ok"]:
            total += r["count"]
            print(f"  ✅ {r['label']:<10} {r['count']:>4} items  ({r['elapsed']}s)")
        else:
            print(f"  ❌ {r['label']:<10} {r['error']}")
    print(f"  --- TOTAL: {total} items across {len(results)} sites ---")
    print("--------------------")

    await browser_manager.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--site",
        choices=list(SITES.keys()),
        help="Run a single site instead of all 5",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Per-site item limit (default 50; use --full for unlimited)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Unlimited per-site (sets limit=9999, scrapes until pagination ends)",
    )
    args = parser.parse_args()

    sites = [args.site] if args.site else list(SITES.keys())
    limit = 9999 if args.full else args.limit

    asyncio.run(main(sites, limit))
