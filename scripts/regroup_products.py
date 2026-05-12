"""
Re-evaluate all ProductGroup assignments using the current matcher logic.

Reason: a bug in `MatcherService.get_canonical_name` caused different products
of unknown brands (brands not in `PerfumeNormalizer.BRANDS`) to collapse into
the same canonical name (e.g. "Emperor Blue EDP"), which then merged them into
one ProductGroup via `ON CONFLICT DO NOTHING`. Bug is fixed in matcher.py, but
existing rows still carry wrong `group_id` values — this script repairs them.

Algorithm:
  1. Read all Products.
  2. For each product, recompute canonical name via the fixed
     `MatcherService.get_canonical_name(title, brand)`.
  3. Group products by recomputed canonical → that's the desired clustering.
  4. For each cluster:
       - Find an existing ProductGroup with that exact name.
       - If found → set all products in cluster to that group_id.
       - If not found → create a new ProductGroup with that name and reassign.
  5. Delete ProductGroups that end up with zero products.

Usage:
  python scripts/regroup_products.py --dry-run     # report only, no DB writes
  python scripts/regroup_products.py               # apply changes

  # To run against production:
  #   set DATABASE_URL=postgresql+asyncpg://market_user:market_password@46.101.174.12:5432/market_pulse_db
"""
import argparse
import asyncio
import os
import sys
from collections import defaultdict

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from loguru import logger
from sqlalchemy import delete, select, func

from app.core.database import async_session_maker
from app.domain.models import Product, ProductGroup
from app.services.matcher import matcher_service


async def regroup(dry_run: bool) -> None:
    async with async_session_maker() as session:
        products = (await session.execute(select(Product))).scalars().all()
        logger.info(f"Loaded {len(products)} products")

        # Step 1 — cluster by recomputed canonical
        clusters: dict[str, list[Product]] = defaultdict(list)
        for p in products:
            canonical = matcher_service.get_canonical_name(p.title or "", brand=p.brand)
            clusters[canonical].append(p)

        logger.info(f"Computed {len(clusters)} unique canonical clusters")

        # Step 2 — load existing groups, key by name
        groups = (await session.execute(select(ProductGroup))).scalars().all()
        groups_by_name = {g.name: g for g in groups}

        moves = 0
        new_groups = 0
        for canonical, items in clusters.items():
            grp = groups_by_name.get(canonical)
            if not grp:
                if dry_run:
                    logger.info(f"[DRY] would create group '{canonical}' (+{len(items)} products)")
                    new_groups += 1
                    continue
                grp = ProductGroup(name=canonical, category="Perfume")
                session.add(grp)
                await session.flush()
                groups_by_name[canonical] = grp
                new_groups += 1
                logger.info(f"+ Created group '{canonical}'")

            for p in items:
                if p.group_id != grp.id:
                    moves += 1
                    if not dry_run:
                        p.group_id = grp.id
                        session.add(p)

        # Step 3 — drop orphan groups
        orphan_q = (
            select(ProductGroup)
            .outerjoin(Product, Product.group_id == ProductGroup.id)
            .group_by(ProductGroup.id)
            .having(func.count(Product.id) == 0)
        )
        orphans = (await session.execute(orphan_q)).scalars().all()

        logger.info(
            f"Summary: {moves} products to move · {new_groups} new groups · {len(orphans)} orphan groups"
        )

        if dry_run:
            logger.info("DRY RUN — no changes written")
            return

        if orphans:
            ids = [g.id for g in orphans]
            await session.execute(delete(ProductGroup).where(ProductGroup.id.in_(ids)))
            logger.info(f"Deleted {len(orphans)} orphan groups")

        await session.commit()
        logger.info("✅ Regroup committed")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report only, do not modify DB")
    args = ap.parse_args()

    db_url = os.environ.get("DATABASE_URL", "(default from app/.env)")
    logger.info(f"Target DB: {db_url}")
    asyncio.run(regroup(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
