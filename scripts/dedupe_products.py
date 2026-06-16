"""De-duplicate Product rows that represent the SAME physical listing.

Why this exists
---------------
Notino (and some legacy scrapes) created several Product rows for one product:
the site serves the same item under two URL forms —

    https://www.notino.lv/hermes/terre-dhermes-smarzas-vriesiem/
    https://www.notino.lv/hermes/terre-dhermes-smarzas-vriesiem/p-81337/

Each form became its own Product with its own (often stale) price, so the
dashboard, product page ("2 listings"), catalog and analytics all showed the
same item repeated with different prices.

What it does
------------
Groups products by (normalized_url, volume) — normalization strips a trailing
"/p-<digits>/" id — keeps the FRESHEST row (latest `last_seen`, which holds the
correct current price), re-points its PriceHistory and Favorites onto the
keeper, then deletes the stale duplicates.

Because normalization only removes the numeric "/p-<id>/" suffix (the slug,
which is unique per product, is preserved) it cannot merge two genuinely
different products. Rows whose URLs are already identical are also collapsed
(those are pure race-condition leftovers).

Safety
------
* DRY-RUN by default — prints exactly what it WOULD change, touches nothing.
* Pass --apply to actually modify the database.
* BACK UP THE DB FIRST (pg_dump) before running with --apply.

Usage (inside the app container):
    python scripts/dedupe_products.py            # dry-run, shows the plan
    python scripts/dedupe_products.py --apply    # performs the cleanup
"""
import asyncio
import re
import sys
from collections import defaultdict
from datetime import datetime

from sqlalchemy import select, update

from app.core.database import async_session
from app.domain.models import Product, PriceHistory, Favorite


_P_SUFFIX = re.compile(r"/p-\d+/?$")


def normalize_url(url: str | None) -> str:
    """Strip the trailing '/p-<digits>/' product-id so the two URL forms of the
    same Notino listing collapse to one canonical key."""
    if not url:
        return ""
    return _P_SUFFIX.sub("/", url.strip())


async def main(apply: bool) -> None:
    async with async_session() as db:
        products = (await db.execute(select(Product))).scalars().all()
        print(f"Total products in DB: {len(products)}")

        groups: dict[tuple, list[Product]] = defaultdict(list)
        for p in products:
            key = (normalize_url(p.url), (p.volume or "").lower())
            groups[key].append(p)

        dupe_groups = {k: v for k, v in groups.items() if len(v) > 1}
        rows_to_remove = sum(len(v) - 1 for v in dupe_groups.values())
        print(f"Duplicate groups (same canonical-url + volume): {len(dupe_groups)}")
        print(f"Duplicate rows that would be removed:           {rows_to_remove}")
        print("-" * 78)

        removed = 0
        # Worst offenders first for readable output
        for key, rows in sorted(dupe_groups.items(), key=lambda kv: -len(kv[1])):
            # Freshest row wins — it carries the correct current price.
            rows.sort(key=lambda p: p.last_seen or datetime.min, reverse=True)
            keeper = rows[0]
            losers = rows[1:]
            print(f"KEEP id={keeper.id} vol={key[1]!r} price={keeper.last_price} "
                  f"seen={keeper.last_seen:%Y-%m-%d}  url={key[0]}")
            for loser in losers:
                print(f"   DROP id={loser.id} price={loser.last_price} "
                      f"seen={loser.last_seen:%Y-%m-%d}  url={loser.url}")
                if not apply:
                    continue
                # 1) Re-point price history onto the keeper (preserve data).
                await db.execute(
                    update(PriceHistory)
                    .where(PriceHistory.product_id == loser.id)
                    .values(product_id=keeper.id)
                )
                # 2) Move favorites; if the user already favorited the keeper the
                #    (user_id, product_id) unique constraint would trip, so drop
                #    the redundant favorite instead of re-pointing it.
                fav_rows = (await db.execute(
                    select(Favorite).where(Favorite.product_id == loser.id)
                )).scalars().all()
                for fav in fav_rows:
                    already = (await db.execute(
                        select(Favorite.id).where(
                            Favorite.user_id == fav.user_id,
                            Favorite.product_id == keeper.id,
                        )
                    )).first()
                    if already:
                        await db.delete(fav)
                    else:
                        fav.product_id = keeper.id
                await db.flush()
                # 3) Delete the duplicate product.
                await db.delete(loser)
                removed += 1

        print("-" * 78)
        if apply:
            await db.commit()
            print(f"DONE. Removed {removed} duplicate products.")
        else:
            print("DRY-RUN only. Nothing was changed. "
                  "Re-run with --apply to perform the cleanup.")


if __name__ == "__main__":
    asyncio.run(main(apply="--apply" in sys.argv))
