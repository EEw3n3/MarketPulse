"""
Backfill PriceHistory with realistic synthetic 90-day price walks.

PROBLEM SOLVED HERE: the first version walked randomly around current_price
ignoring real PriceHistory entries. Result: where a real "initial" event sat
at the old price (e.g. 89.99 on Apr 27), the chart showed a single weird
spike above a sea of synthetic 65€ noise. Also density was too low for the
1-week view (~0.84 events expected per week → mostly empty).

NEW algorithm:
  • Treat real (non-synthetic) PriceHistory entries as ANCHORS on a trajectory.
  • Trajectory: [(date, price), ...] real entries sorted ASC, ending implicitly
    at (today, current_price).
  • For each day in the synthetic window, the baseline price is linearly
    interpolated along this trajectory.
  • A synthetic event = baseline * (1 + small Gaussian noise), clamped to
    ±15% of baseline.
  • Recent days are denser (25% chance per day for last 14 days, 13% else)
    so the 1W view always has points.
  • All synthetic rows tagged change_type='synthetic' → trivial rollback:
      DELETE FROM price_history WHERE change_type = 'synthetic';

Result: synthetic data smoothly transitions BETWEEN real points (no more
spikes), and recent week is dense.

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
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.database import async_session_maker
from app.domain.models import Product, PriceHistory


# Tuning constants — denser + tighter than first pass to look like real
# day-to-day fluctuations rather than smooth Bezier arcs.
SIGMA_DAILY = 0.035           # Gaussian std dev around baseline (~3.5%)
NOISE_CLAMP = 0.09            # max ±9% deviation from baseline
PROB_RECENT = 0.55            # daily event probability for last 14 days
PROB_OLDER = 0.30             # daily event probability for older days
RECENT_DAYS = 14              # cutoff between recent and older


def _interp_baseline(
    t: datetime,
    trajectory: list[tuple[datetime, float]],
    pre_anchor_drift: float = 0.0,
) -> float:
    """Linear interpolation across the (date, price) anchor list (sorted ASC).

    For dates BEFORE the earliest anchor, applies a small linear drift
    (`pre_anchor_drift` fraction per day older) so the pre-anchor period
    doesn't look like a perfectly flat line.
    """
    if not trajectory:
        return 0.0
    if t <= trajectory[0][0]:
        days_before = (trajectory[0][0] - t).total_seconds() / 86400
        return trajectory[0][1] * (1 + pre_anchor_drift * days_before)
    if t >= trajectory[-1][0]:
        return trajectory[-1][1]
    for i in range(len(trajectory) - 1):
        t1, p1 = trajectory[i]
        t2, p2 = trajectory[i + 1]
        if t1 <= t <= t2:
            span = (t2 - t1).total_seconds()
            if span <= 0:
                return p2
            ratio = (t - t1).total_seconds() / span
            return p1 + (p2 - p1) * ratio
    return trajectory[-1][1]


def generate_events_for_product(
    current_price: float,
    real_history: list[tuple[datetime, float]],
    days: int,
    now: datetime,
    rng: random.Random,
) -> list[tuple[datetime, Decimal]]:
    """Generate (parsed_at, price) tuples using a trajectory built from real points."""
    # Build trajectory anchors. Append (now, current_price) so the walk lands at today's price.
    trajectory = list(real_history)
    if not trajectory or trajectory[-1][0] < now - timedelta(hours=1):
        trajectory.append((now, current_price))
    # Real history sometimes has duplicate timestamps — dedupe by sorted unique
    trajectory.sort(key=lambda x: x[0])

    # Per-product pre-anchor drift: small bias in the pre-anchor flat region so
    # different products don't all look like a horizontal line on the left side.
    # Range ±0.3% per day — over 75 pre-anchor days = ±22.5% drift envelope.
    pre_drift = rng.uniform(-0.003, 0.003)

    events: list[tuple[datetime, Decimal]] = []
    for d in range(1, days + 1):
        # Random hour/minute within the day for natural-looking spread
        day_ts = now - timedelta(days=d, hours=rng.randint(0, 23), minutes=rng.randint(0, 59))

        # Skip if a real point already exists within ±6h of this slot — avoid clumping
        if any(abs((rt - day_ts).total_seconds()) < 6 * 3600 for rt, _ in real_history):
            continue

        baseline = _interp_baseline(day_ts, trajectory, pre_anchor_drift=pre_drift)
        if baseline <= 0:
            continue

        # Daily noise
        noise = rng.gauss(0, SIGMA_DAILY)
        noise = max(-NOISE_CLAMP, min(NOISE_CLAMP, noise))
        price = baseline * (1 + noise)
        # Tight clamp to ±15% of baseline regardless of noise outliers
        price = max(baseline * (1 - NOISE_CLAMP), min(baseline * (1 + NOISE_CLAMP), price))

        # Density: 1W view needs dense data, older days can be sparser
        prob = PROB_RECENT if d <= RECENT_DAYS else PROB_OLDER
        if rng.random() < prob:
            events.append((day_ts, Decimal(f"{price:.2f}")))

    events.sort(key=lambda e: e[0])
    return events


async def seed(dry_run: bool, days: int, site: str | None, seed_val: int | None) -> None:
    rng = random.Random(seed_val) if seed_val is not None else random.Random()
    now = datetime.utcnow()

    async with async_session_maker() as session:
        stmt = select(Product).options(selectinload(Product.history)).where(
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

        existing = (await session.execute(
            select(func.count()).select_from(PriceHistory).where(PriceHistory.change_type == "synthetic")
        )).scalar_one()
        if existing > 0:
            logger.warning(
                f"⚠️  {existing} synthetic rows already exist. "
                f"Running again ADDS more. Rollback first if you want a clean state:\n"
                f"   docker compose exec db psql -U market_user market_pulse_db "
                f"-c \"DELETE FROM price_history WHERE change_type = 'synthetic';\""
            )

        total_events = 0
        sample_logged = 0
        for p in products:
            real = sorted(
                [(h.parsed_at, float(h.price)) for h in p.history if h.change_type != "synthetic"],
                key=lambda x: x[0],
            )
            events = generate_events_for_product(
                current_price=float(p.last_price),
                real_history=real,
                days=days,
                now=now,
                rng=rng,
            )
            if not events:
                continue
            total_events += len(events)

            if sample_logged < 3:
                prices = [float(e[1]) for e in events]
                logger.info(
                    f"  sample [{p.id}] {p.title[:40]!r} "
                    f"current={float(p.last_price):.2f}€ real_points={len(real)} "
                    f"synthetic={len(events)} range={min(prices):.2f}–{max(prices):.2f}€"
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
        logger.info(
            f"Generated {total_events} synthetic events across {len(products)} products "
            f"(avg {avg:.1f}/product, density {avg / days * 100:.0f}%/day)"
        )

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
