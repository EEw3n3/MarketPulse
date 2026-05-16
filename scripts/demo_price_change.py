"""Demo-only: change a product's price and fire the same notification
pipeline the real scraper uses. Used to demonstrate Telegram + Email alerts
without waiting for a scrape to detect a natural price change.

Usage:
  python scripts/demo_price_change.py <product_id> <new_price>

Examples:
  python scripts/demo_price_change.py 1207 99.99
  docker compose exec app python scripts/demo_price_change.py 1207 49.99

What happens:
  1. Looks up the product.
  2. Saves current price → product.old_price; sets product.last_price → new.
  3. Inserts a PriceHistory row with change_type='price_up' or 'price_down'.
  4. Commits.
  5. Calls dispatcher.dispatch_price_alert(...) — same call site the scraper uses,
     so subscribers with alert_enabled=True get Telegram + Email alerts.

Notes:
  * The user must have alert_enabled=True on their Favorite for this product.
  * For Telegram to fire: preferences.telegram_chat_id must be set (user
    completed the /connect flow in the bot).
  * For Email: preferences.notification_channels must include 'email' AND
    SMTP_* env vars must be configured on the server.
  * Notification threshold: if |percent_change| < user.notification_threshold,
    the alert is silently skipped. Default threshold is 5%, so a change of
    ≥5% from the previous price is required.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime
from decimal import Decimal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from loguru import logger
from sqlalchemy import select

from app.core.database import async_session_maker
from app.domain.models import Product, PriceHistory
from app.services.notification_dispatcher import dispatcher


def _pct(new: float, old: float) -> float:
    if not old or old <= 0:
        return 0.0
    return (new - old) / old * 100.0


async def change_price(product_id: int, new_price: float) -> None:
    async with async_session_maker() as session:
        product = await session.get(Product, product_id)
        if not product:
            logger.error(f"Product id={product_id} not found")
            return

        old_price = float(product.last_price or 0)
        if old_price == new_price:
            logger.warning(f"Price unchanged ({new_price}€) — nothing to do")
            return

        pct = _pct(new_price, old_price)
        change_type = "price_down" if new_price < old_price else "price_up"

        # 1. Update product
        product.old_price = product.last_price
        product.last_price = Decimal(str(new_price))
        product.last_seen = datetime.utcnow()
        session.add(product)

        # 2. Insert history
        history = PriceHistory(
            product_id=product.id,
            price=Decimal(str(new_price)),
            in_stock=bool(product.is_available),
            parsed_at=datetime.utcnow(),
            change_type=change_type,
        )
        session.add(history)

        await session.commit()
        await session.refresh(history)
        logger.info(
            f"💰 [{product.id}] '{product.title[:50]}': {old_price:.2f}€ → {new_price:.2f}€ "
            f"({pct:+.1f}%, change_type={change_type})"
        )

        # 3. Dispatch — SAME function the scraper calls in _flush_candidates
        try:
            await dispatcher.dispatch_price_alert(session, product, history, pct)
            logger.info("📨 Notification dispatch invoked. Check Telegram + inbox.")
        except Exception as exc:
            logger.exception(f"Dispatch failed: {exc}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("product_id", type=int, help="Product ID (find via SELECT id FROM product)")
    ap.add_argument("new_price", type=float, help="Target price in € (must differ from current)")
    args = ap.parse_args()

    logger.info(f"Target DB: {os.environ.get('DATABASE_URL', '(default)')}")
    asyncio.run(change_price(args.product_id, args.new_price))


if __name__ == "__main__":
    main()
