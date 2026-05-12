"""
Re-apply normalizer NOISE removal to existing Product.title values in-place.

Reason: when new NOISE patterns are added to PerfumeNormalizer (e.g. Latvian
'(ierobežota daudzuma prece)' artifact in Session 17), they only affect FUTURE
scrapes. Existing rows carry the dirty titles until the next full scrape. On
environments where scraping can't run (server is Cloudflare-blocked), this
script repairs titles directly in the DB.

Algorithm:
  1. Read all products.
  2. For each, apply current NOISE regex patterns to its title.
  3. UPDATE Product.title only if changed AND result is still >= 3 chars.

Safe to run repeatedly — no-op for already-clean titles.

Usage:
  docker compose exec app python scripts/renormalize_titles.py --dry-run
  docker compose exec app python scripts/renormalize_titles.py
"""
import argparse
import asyncio
import os
import re
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from loguru import logger
from sqlalchemy import select

from app.core.database import async_session_maker
from app.domain.models import Product
from app.services.normalizer import PerfumeNormalizer


async def renormalize(dry_run: bool) -> None:
    async with async_session_maker() as session:
        products = (await session.execute(select(Product))).scalars().all()
        logger.info(f"Loaded {len(products)} products")

        changes = 0
        samples: list[tuple[str, str]] = []
        for p in products:
            original = p.title or ""
            cleaned = original
            for noise_pat in PerfumeNormalizer.NOISE:
                cleaned = re.sub(noise_pat, "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip(" ,.:;?!'\"|-")
            # Skip if cleanup produced empty/too-short result (preserve original)
            if not cleaned or len(cleaned) < 3:
                continue
            if cleaned != original:
                changes += 1
                if len(samples) < 15:
                    samples.append((original, cleaned))
                if not dry_run:
                    p.title = cleaned
                    session.add(p)

        logger.info(f"{changes} of {len(products)} titles will change")
        for orig, new in samples:
            logger.info(f"  {orig!r}\n  → {new!r}")

        if dry_run:
            logger.info("DRY RUN — no changes written")
            return

        await session.commit()
        logger.info(f"✅ {changes} titles renormalized")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report only")
    args = ap.parse_args()
    db_url = os.environ.get("DATABASE_URL", "(default from app/.env)")
    logger.info(f"Target DB: {db_url}")
    asyncio.run(renormalize(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
