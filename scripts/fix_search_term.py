"""
Repair Product.search_term values that got set to 'Unknown Shop' (or other
non-canonical values) by deriving the correct store domain from product.url.

Reason: prior scraper used `search_term=rule.site_name`, but ScrapingRule.site_name
defaulted to 'Unknown Shop' when AI didn't populate it. Result: thousands of
products on prod have search_term='Unknown Shop' and are invisible to the
catalog's store filter (which does `LIKE '%notino%'` etc).

Algorithm:
  1. Read all products.
  2. For each, parse the URL's hostname → canonical domain (e.g. 'notino.lv').
  3. If parsed domain differs from current search_term, update.

Idempotent — running twice is a no-op.

Usage:
  docker compose exec app python scripts/fix_search_term.py --dry-run
  docker compose exec app python scripts/fix_search_term.py
"""
import argparse
import asyncio
import os
import sys
from collections import Counter
from urllib.parse import urlparse

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from loguru import logger
from sqlalchemy import select

from app.core.database import async_session_maker
from app.domain.models import Product


# Known canonical store domains — keyed for matching substrings inside URLs.
KNOWN_DOMAINS = ["notino.lv", "douglas.lv", "220.lv", "makeup.lv", "1a.lv"]


def derive_domain(url: str | None) -> str | None:
    """Return canonical 'foo.lv' domain from a URL, or None if unparseable."""
    if not url:
        return None
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return None
    if not host:
        # url might be a path without scheme — fall back to substring match
        host = url.lower()
    host = host.replace("www.", "")
    # Strict match against known store domains
    for d in KNOWN_DOMAINS:
        if d in host:
            return d
    return None


async def fix(dry_run: bool) -> None:
    async with async_session_maker() as session:
        products = (await session.execute(select(Product))).scalars().all()
        logger.info(f"Loaded {len(products)} products")

        changes = 0
        unchanged = 0
        unmatched = 0
        before_counter: Counter[str] = Counter()
        after_counter: Counter[str] = Counter()

        for p in products:
            before_counter[p.search_term or "<empty>"] += 1
            derived = derive_domain(p.url)
            if derived is None:
                unmatched += 1
                after_counter[p.search_term or "<empty>"] += 1
                continue
            if p.search_term == derived:
                unchanged += 1
                after_counter[derived] += 1
                continue
            changes += 1
            after_counter[derived] += 1
            if not dry_run:
                p.search_term = derived
                session.add(p)

        logger.info("Before (current state):")
        for st, n in before_counter.most_common():
            logger.info(f"  {st!r:35} {n}")

        logger.info("After (planned state):")
        for st, n in after_counter.most_common():
            logger.info(f"  {st!r:35} {n}")

        logger.info(f"Summary: {changes} to update · {unchanged} already correct · {unmatched} unmatched (kept as-is)")

        if dry_run:
            logger.info("DRY RUN — no rows written")
            return

        await session.commit()
        logger.info(f"✅ {changes} products committed with corrected search_term")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report only, no DB writes")
    args = ap.parse_args()
    logger.info(f"Target DB: {os.environ.get('DATABASE_URL', '(default)')}")
    asyncio.run(fix(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
