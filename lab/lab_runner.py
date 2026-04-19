"""
MarketPulse Lab Runner — Multi-site stress test
Runs all 5 sites sequentially, collects quality metrics, prints summary.

Usage:
  python lab/lab_runner.py           # stress test: 20 items per site, regenerate rules
  python lab/lab_runner.py --full    # full run: all items per site, reuse existing rules
  python lab/lab_runner.py --clear   # wipe stale Product/PriceHistory rows before run
"""
import asyncio
import sys
import os
import time
from decimal import Decimal
from loguru import logger
from sqlmodel import SQLModel, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.domain.models import ScrapingRule, Product
from app.services.scraper import scraper_service
from app.core.client import stealth_client

# --- LAB CONFIGURATION ---
LAB_DB_URL = "sqlite+aiosqlite:///lab/lab_test.db"
lab_engine = create_async_engine(LAB_DB_URL, echo=False)

FULL_RUN   = "--full"  in sys.argv
CLEAR_DATA = "--clear" in sys.argv   # wipe all Product/PriceHistory rows before run
# 9999 = effectively unlimited; scraper stops on its own when pagination ends
_FULL_LIMIT = 100

# --skip notino,douglas  → comma-separated site labels to exclude
_skip_arg = next((a for a in sys.argv if a.startswith("--skip=")), None)
SKIP_LABELS = {s.strip().lower() for s in _skip_arg.replace("--skip=", "").split(",")} if _skip_arg else set()

# All 5 production sites
# stress test: limit=20, force_refresh=True (regenerate rules each time)
# full run:    limit=9999, force_refresh=False (reuse already-verified rules)
TEST_SITES = [
    {
        "url": "https://www.notino.lv/viriesu-smarzas/",
        "label": "Notino.lv",
        "force_refresh": not FULL_RUN,
        "limit": _FULL_LIMIT if FULL_RUN else 20,
    },
    {
        "url": "https://www.douglas.lv/lv/katalogs/smarzas/viriesu-smarzas/smarzas/",
        "label": "Douglas.lv",
        "force_refresh": not FULL_RUN,
        "limit": _FULL_LIMIT if FULL_RUN else 20,
    },
    {
        "url": "https://makeup.lv/categorys/3218/",
        "label": "Makeup.lv",
        "force_refresh": not FULL_RUN,
        "limit": _FULL_LIMIT if FULL_RUN else 20,
    },
    {
        "url": "https://220.lv/lv/smarzas/viriesu_smarzas",
        "label": "220.lv",
        "force_refresh": not FULL_RUN,
        "limit": _FULL_LIMIT if FULL_RUN else 20,
    },
    {
        "url": "https://www.1a.lv/c/smarzas-un-kosmetika/viriesu-smarzas/viriesu-smarzas/30j",
        "label": "1a.lv",
        "force_refresh": not FULL_RUN,
        "limit": _FULL_LIMIT if FULL_RUN else 20,
    },
]


async def init_lab_db():
    async with lab_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    logger.info("🧪 Lab Database initialized.")


async def clear_product_data():
    """Wipe all Product and PriceHistory rows (keeps ScrapingRules intact)."""
    from app.domain.models import PriceHistory
    async with lab_engine.begin() as conn:
        await conn.execute(PriceHistory.__table__.delete())
        await conn.execute(Product.__table__.delete())
    logger.warning("🗑️  Cleared all Product and PriceHistory rows from lab DB.")


async def clear_rule(session: AsyncSession, domain: str):
    """Delete existing rule for domain before re-testing."""
    stmt = select(ScrapingRule).where(ScrapingRule.domain == domain)
    result = await session.execute(stmt)
    rule = result.scalar_one_or_none()
    if rule:
        await session.delete(rule)
        await session.commit()
        logger.warning(f"🗑️  Cleared stale rule for {domain}")


async def run_site_test(session: AsyncSession, site_url: str, label: str, limit: int) -> dict:
    """
    Run a single site test and return quality metrics.
    Returns a metrics dict with all quality data.
    """
    from app.core.registry import register_domain
    from app.services.ai_generator import ai_generator
    from app.core.browser import browser_manager

    t_start = time.time()
    metrics = {
        "label": label,
        "url": site_url,
        "total": 0,
        "available": 0,
        "unavailable": 0,
        "with_price": 0,
        "with_brand": 0,
        "with_volume": 0,
        "with_group": 0,
        "zero_prices": 0,
        "no_brand": 0,
        "no_volume": 0,
        "elapsed": 0.0,
        "status": "❌ FAILED",
        "error": None,
    }

    try:
        register_domain(site_url)

        # Fetch initial HTML
        response = await browser_manager.get_page_content(site_url)
        if not response or not response.get("html"):
            metrics["error"] = "Failed to fetch HTML"
            return metrics

        html = response["html"]

        # Save debug HTML per site
        debug_path = f"lab/debug_{label.replace('.', '_').replace(' ', '_').lower()}.html"
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(html)

        # Get or create scraping rule
        rule = await ai_generator.get_or_create_rule(session, site_url, html)
        if not rule:
            metrics["error"] = "AI failed to create rule"
            return metrics

        logger.info(f"🧬 Rule loaded: {rule.site_name} | container: {rule.container_css}")

        # Run scraper
        items = await scraper_service.scrape_catalog(
            session=session,
            start_url=site_url,
            initial_html=html,
            max_items=limit,
            enable_price_filter=False,
        )

        elapsed = time.time() - t_start
        metrics["elapsed"] = elapsed

        if not items:
            metrics["error"] = "Scraper returned 0 items"
            return metrics

        metrics["total"] = len(items)
        metrics["status"] = "✅ OK"

        # Check DB for what was actually saved — filter by exact URLs from this run
        scraped_urls = [item.url for item in items if item.url]
        if scraped_urls:
            stmt = select(Product).where(Product.url.in_(scraped_urls))
            saved = (await session.execute(stmt)).scalars().all()

            for p in saved:
                # Separate unavailable (legitimately out of stock) from actual bugs
                if not p.is_available and (p.last_price is None or p.last_price == 0):
                    metrics["unavailable"] += 1
                    continue  # Don't count unavailable items in quality metrics

                metrics["available"] += 1

                if p.last_price and p.last_price > 0:
                    metrics["with_price"] += 1
                else:
                    metrics["zero_prices"] += 1

                if p.brand:
                    metrics["with_brand"] += 1
                else:
                    metrics["no_brand"] += 1

                if p.volume:
                    metrics["with_volume"] += 1
                else:
                    metrics["no_volume"] += 1

                if p.group_id:
                    metrics["with_group"] += 1

    except Exception as e:
        metrics["error"] = str(e)
        logger.error(f"💥 [{label}] Exception: {e}")

    return metrics


def print_summary(all_metrics: list[dict]):
    """Print a clean summary table of all site results."""
    W = 88
    print()
    print(f"╔{'═' * W}╗")
    print(f"║{'  🧪  MARKETPULSE STRESS TEST — RESULTS SUMMARY':<{W}}║")
    print(f"╠{'═' * W}╣")
    print(f"║  {'Site':<14} {'Status':<10} {'Avail':>6} {'OOS':>5} {'Price%':>7} {'Brand%':>7} {'Vol%':>7} {'Chain%':>7} {'Time':>7}  ║")
    print(f"╠{'─' * W}╣")

    total_items = 0
    total_avail = 0
    total_ok = 0

    for m in all_metrics:
        n = m["total"]
        a = m["available"]
        total_items += n
        total_avail += a

        # Calculate percentages based on AVAILABLE items only (not total)
        price_pct = f"{m['with_price'] / a * 100:.0f}%" if a else "—"
        brand_pct = f"{m['with_brand'] / a * 100:.0f}%" if a else "—"
        vol_pct   = f"{m['with_volume'] / a * 100:.0f}%" if a else "—"
        chain_pct = f"{m['with_group'] / a * 100:.0f}%" if a else "—"
        elapsed   = f"{m['elapsed']:.1f}s"
        oos       = m["unavailable"]

        status = m["status"]
        if m["status"] == "✅ OK":
            total_ok += 1

        err = f"  ← {m['error']}" if m.get("error") and m["status"] != "✅ OK" else ""

        print(f"║  {m['label']:<14} {status:<10} {a:>6} {oos:>5} {price_pct:>7} {brand_pct:>7} {vol_pct:>7} {chain_pct:>7} {elapsed:>7}  ║{err}")

    print(f"╠{'═' * W}╣")
    overall = "✅ ALL PASS" if total_ok == len(all_metrics) else f"⚠️  {total_ok}/{len(all_metrics)} PASSED"
    print(f"║  {overall:<20} Available: {total_avail} / Total: {total_items:<8}{'':<{W-52}}║")
    print(f"╚{'═' * W}╝")
    print()

    # Detailed issues report
    issues_found = False
    for m in all_metrics:
        n = m["total"]
        if n == 0:
            continue
        a = m["available"]
        site_issues = []
        if m["zero_prices"] > 0:
            site_issues.append(f"{m['zero_prices']} available items with zero price (BUG)")
        if m["unavailable"] > 0:
            site_issues.append(f"{m['unavailable']} items out of stock (excluded from metrics)")
        if a > 0 and m["no_brand"] / a > 0.3:
            site_issues.append(f"{m['no_brand']} items missing brand ({m['no_brand']/a*100:.0f}%)")
        if a > 0 and m["no_volume"] / a > 0.5:
            site_issues.append(f"{m['no_volume']} items missing volume ({m['no_volume']/a*100:.0f}%)")
        if a > 0 and m["with_group"] / a < 0.5:
            site_issues.append(f"Low chaining rate: only {m['with_group']}/{a} got a ProductGroup")

        if site_issues:
            issues_found = True
            print(f"⚠️  [{m['label']}] Issues:")
            for issue in site_issues:
                print(f"     - {issue}")

    if not issues_found:
        print("✅ No critical data quality issues found across all sites.")
    print()


async def main():
    if not os.path.exists("lab"):
        os.makedirs("lab")

    await init_lab_db()
    if CLEAR_DATA:
        await clear_product_data()
    await stealth_client.init_session()

    async_session = sessionmaker(lab_engine, class_=AsyncSession, expire_on_commit=False)
    all_metrics = []

    for site in TEST_SITES:
        if site["label"].lower().replace(".lv", "") in SKIP_LABELS or site["label"].lower() in SKIP_LABELS:
            print(f"\n  ⏭️  Skipping {site['label']} (--skip)")
            continue

        print()
        print(f"{'='*55}")
        print(f"  🧪 TESTING: {site['label']}")
        print(f"  URL: {site['url']}")
        print(f"{'='*55}")

        # Clear stale rule if force_refresh
        if site.get("force_refresh"):
            async with async_session() as session:
                from urllib.parse import urlparse
                domain = urlparse(site["url"]).netloc.replace("www.", "")
                await clear_rule(session, domain)

        async with async_session() as session:
            metrics = await run_site_test(session, site["url"], site["label"], site["limit"])
            all_metrics.append(metrics)

        logger.info(f"✔ [{site['label']}] done — {metrics['total']} items in {metrics['elapsed']:.1f}s")

    # Cleanup
    from app.core.browser import browser_manager
    await browser_manager.stop()
    await stealth_client.close()

    # Print full summary
    print_summary(all_metrics)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
