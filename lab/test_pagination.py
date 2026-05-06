"""Pagination verification — runs ONE site, captures page-by-page events, checks for duplicates.

Usage:
    python lab/test_pagination.py notino           # default limit=150
    python lab/test_pagination.py 1a --limit=200
    python lab/test_pagination.py douglas --limit=100
    python lab/test_pagination.py makeup --limit=200
    python lab/test_pagination.py 220 --limit=150

Each site uses its own SQLite DB (lab/pagination_<site>.db) so runs are isolated.
"""
import asyncio
import os
import sys
import time

# Force UTF-8 output on Windows terminals (CP1251 can't encode emoji from log messages)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, select

from app.core.browser import browser_manager
from app.core.registry import register_domain
from app.domain.models import Product, ScrapingRule  # noqa: F401  (registers tables)
from app.services.ai_generator import ai_generator
from app.services.scraper import scraper_service

SITES = {
    "notino":  ("https://www.notino.lv/viriesu-smarzas/", "notino.lv"),
    "douglas": ("https://www.douglas.lv/lv/katalogs/smarzas/viriesu-smarzas/smarzas/", "douglas.lv"),
    "makeup":  ("https://makeup.lv/categorys/3218/", "makeup.lv"),
    "220":     ("https://220.lv/lv/smarzas/viriesu_smarzas", "220.lv"),
    "1a":      ("https://www.1a.lv/c/smarzas-un-kosmetika/viriesu-smarzas/viriesu-smarzas/30j", "1a.lv"),
}


def parse_args():
    if len(sys.argv) < 2 or sys.argv[1] not in SITES:
        print(f"Usage: python lab/test_pagination.py <site> [--limit=N]")
        print(f"Sites: {', '.join(SITES.keys())}")
        sys.exit(1)
    site = sys.argv[1]
    limit = 150
    for arg in sys.argv[2:]:
        if arg.startswith("--limit="):
            limit = int(arg.split("=", 1)[1])
    return site, limit


# Pagination event tracker — populated by a custom loguru sink.
PAGE_EVENTS: list[str] = []


def page_sink(message):
    rec = message.record["message"]
    if any(k in rec for k in ("Page", "page=", "offset=", "Navigating", "flushed", "Cards:")):
        PAGE_EVENTS.append(rec)


async def run(site_key: str, limit: int):
    url, domain = SITES[site_key]
    db_path = f"lab/pagination_{site_key}.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"

    # Register pagination event sink
    logger.add(page_sink, level="INFO")

    print(f"\n{'=' * 78}")
    print(f"  PAGINATION TEST - {site_key} ({domain})")
    print(f"  Limit: {limit} items   |   DB: {db_path}")
    print(f"{'=' * 78}\n")

    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        # Add concentration_css column if missing (for old lab DBs)
        rows = (await conn.execute(text("PRAGMA table_info(scrapingrule)"))).fetchall()
        if "concentration_css" not in {r[1] for r in rows}:
            await conn.execute(text("ALTER TABLE scrapingrule ADD COLUMN concentration_css TEXT"))

    session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Clear previous products for clean run
    async with session_maker() as session:
        await session.execute(text("DELETE FROM pricehistory"))
        await session.execute(text("DELETE FROM product"))
        await session.commit()

    register_domain(url)

    async with session_maker() as session:
        # Fetch initial HTML
        response = await browser_manager.get_page_content(url)
        if not response or not response.get("html"):
            print("FAIL: Failed to fetch initial HTML")
            return
        html = response["html"]

        # Get or create rule
        rule = await ai_generator.get_or_create_rule(session, url, html)
        if not rule:
            print("FAIL: AI failed to create scraping rule")
            return
        print(f"Rule: {rule.site_name} | container: {rule.container_css}\n")

        # Run scraper
        t0 = time.time()
        items = await scraper_service.scrape_catalog(
            session=session,
            start_url=url,
            initial_html=html,
            max_items=limit,
            enable_price_filter=False,
        )
        elapsed = time.time() - t0

    # Analyze DB
    async with session_maker() as session:
        rows = (await session.execute(select(Product))).scalars().all()

    urls = [p.url for p in rows if p.url]
    titles = [p.title for p in rows if p.title]
    # Duplicate (url, volume) pairs = real scraper bug; duplicate urls alone = expected (variants)
    url_vol_pairs = [(p.url, p.volume) for p in rows if p.url]
    dup_url_vol = len(url_vol_pairs) - len(set(url_vol_pairs))
    dup_urls = len(urls) - len(set(urls))  # informational only
    dup_titles = len(titles) - len(set(titles))

    # Print captured pagination events
    print(f"\n{'-' * 78}")
    print("  PAGINATION TIMELINE")
    print(f"{'-' * 78}")
    for ev in PAGE_EVENTS[-40:]:  # last 40 page events
        print(f"  {ev}")

    print(f"\n{'=' * 78}")
    print("  SUMMARY")
    print(f"{'=' * 78}")
    print(f"  Items returned by scraper:  {len(items)}")
    print(f"  Items saved in DB:          {len(rows)}")
    print(f"  Unique URLs:                {len(set(urls))}")
    print(f"  Duplicate URLs (variants):  {dup_urls}  (expected — same product, diff volumes)")
    print(f"  Duplicate (url+vol) pairs:  {dup_url_vol}  (0 = OK)")
    print(f"  Duplicate titles:           {dup_titles}")
    print(f"  Elapsed:                    {elapsed:.1f}s")
    print(f"{'=' * 78}")

    # Verdict — only (url, volume) duplicates indicate a real pagination bug
    print()
    if dup_url_vol > 0:
        print(f"FAIL: {dup_url_vol} duplicate (url+volume) pairs -- scraper revisited same items")
    elif len(rows) < limit * 0.5:
        print(f"WARN: only {len(rows)}/{limit} items collected -- pagination may stop early")
    else:
        print(f"PASS: pagination produced {len(rows)} unique items ({dup_urls} variant-url dupes, expected)")
    print()


if __name__ == "__main__":
    site, limit = parse_args()
    asyncio.run(run(site, limit))
