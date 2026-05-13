"""
Backfill PriceHistory with synthetic 90-day random walk data.

Reason: real price history only accumulates when a scrape detects a price
change (`change_type != "no_change"`). With only 2-3 scrapes so far, most
products have 1-2 history points → PriceChart / MarketTrendChart /
VolatilityScatter look empty. For a pre-demo wrap-up we need plausible
historical data.

Properties of the generated data:
  - 90 days backward from today
  - ~12% chance of a price-change event per day per product
  - Change magnitude: Gaussian (μ=0, σ=5%), clamped to ±15% per step
  - Absolute clamp: walk-back price stays within ±40% of current_price
  - Walk is anchored at current_price (we generate BACKWARDS in time so the
    most-recent synthetic point lands close to today's real price — no
    discontinuity in the chart)
  - All rows tagged `change_type = "synthetic"` for trivial rollback:
      DELETE FROM price_history WHERE change_type = 'synthetic';

Usage:
  docker compose exec app python scripts/seed_synthetic_history.py --dry-run
  docker compose exec app python scripts/seed_synthetic_history.py
  docker compose exec app python scripts/seed_synthetic_history.py --site notino
  docker compose exec app python scripts/seed_synthetic_history.py --days 180
"""
import argparse
import asyncio
import os
import random
import sys
from datetime import datetime, timedelta
from decimal import Decimal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from loguru import logger
from sqlalchemy import select, delete, func

from app.core.database import async_session_maker
from app.domain.models import Product, PriceHistory


CHANGE_PROB_PER_DAY = 0.12
SIGMA_DAILY = 0.05      # 5% one-day std dev
MAX_DAILY_PCT = 0.15    # cap one-day move at ±15%
ABS_BAND_PCT = 0.40     # walk stays within ±40% of current price


def generate_events_for_product(
    current_price: Decimal,
    days: int,
    now: datetime,
    rng: random.Random,
) -> list[tuple[datetime, Decimal]]:
    """Generate (parsed_at, price) tuples walking backwards from today."""
    cur = float(current_price)
    lo = cur * (1 - ABS_BAND_PCT)
    hi = cur * (1 + ABS_BAND_PCT)

    walk = cur
    events: list[tuple[datetime, float]] = []

    # Walk back day-by-day. Note: we want the LATEST synthetic point to be
    # near current_price, so we record events as we step back, then later
    # we'll keep the natural chronological order in DB.
    for d in range(1, days + 1):
        if rng.random() < CHANGE_PROB_PER_DAY:
            delta_pct = rng.gauss(0, SIGMA_DAILY)
            delta_pct = max(-MAX_DAILY_PCT, min(MAX_DAILY_PCT, delta_pct))
            walk = walk * (1 + delta_pct)
            walk = max(lo, min(hi, walk))
            parsed = now - timedelta(days=d, hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
            events.append((parsed, walk))

    # Sort ASC (oldest → newest) so DB order matches chart x-axis
    events.sort(key=lambda e: e[0])
    return [(t, Decimal(f"{p:.2f}")) for t, p in events]


async def seed(dry_run: bool, days: int, site: str | None, seed_val: int | None) -> None:
    rng = random.Random(seed_val) if seed_val is not None else random.Random()
    now = datetime.utcnow()

    async with async_session_maker() as session:
        # Load all products with a non-zero current price
        stmt = select(Product).where(
            Product.last_price.isnot(None),
            Product.last_price > 0,
        )
        if site:
            stmt = stmt.where(func.lower(Product.search_term).like(f"%{site.lower()}%"))
        products = (await session.execute(stmt)).scalars().all()
        logger.info(f"Eligible products: {len(products)} (site filter: {site or 'all'})")

        if not products:
            logger.warning("No products to process — aborting")
            return

        # Count existing synthetic rows for warning
        existing = (await session.execute(
            select(func.count()).select_from(PriceHistory).where(PriceHistory.change_type == "synthetic")
        )).scalar_one()
        if existing > 0:
            logger.warning(
                f"⚠️  {existing} synthetic rows already exist. "
                f"Running again will ADD MORE. Consider rollback first: "
                f"DELETE FROM price_history WHERE change_type = 'synthetic';"
            )

        total_events = 0
        sample_logged = 0
        for p in products:
            events = generate_events_for_product(p.last_price, days, now, rng)
            if not events:
                continue
            total_events += len(events)

            if sample_logged < 3:
                logger.info(
                    f"  sample [{p.id}] {p.title[:40]!r} "
                    f"current={float(p.last_price):.2f}€ events={len(events)} "
                    f"range={float(min(e[1] for e in events)):.2f}–{float(max(e[1] for e in events)):.2f}€"
                )
                sample_logged += 1

            if not dry_run:
                session.add_all([
                    PriceHistory(
                        product_id=p.id,
                        price=price,
                        in_stock=True,
                        parsed_at=parsed_at,
                        change_type="synthetic",
                    )
                    for parsed_at, price in events
                ])

        avg = total_events / max(len(products), 1)
        logger.info(f"Generated {total_events} synthetic events across {len(products)} products (avg {avg:.1f}/product)")

        if dry_run:
            logger.info("DRY RUN — no rows written")
            return

        await session.commit()
        logger.info(f"✅ {total_events} synthetic PriceHistory rows committed")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report only, no DB writes")
    ap.add_argument("--days", type=int, default=90, help="how many days of history to generate (default 90)")
    ap.add_argument("--site", type=str, default=None, help="restrict to products of this site (LIKE on search_term)")
    ap.add_argument("--seed", type=int, default=None, help="random seed for reproducibility")
    args = ap.parse_args()

    logger.info(f"Target DB: {os.environ.get('DATABASE_URL', '(default)')}")
    logger.info(f"Params: days={args.days} site={args.site or 'all'} seed={args.seed}")
    asyncio.run(seed(dry_run=args.dry_run, days=args.days, site=args.site, seed_val=args.seed))


if __name__ == "__main__":
    main()
