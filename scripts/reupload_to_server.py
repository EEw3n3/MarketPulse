"""Re-upload products from LOCAL Docker DB to the production server.

When `scrape_worker.py` fails mid-upload (network blip on batch N), all batches
after the failure are lost — products sit in the local DB but never make it
to the server. This script reads them out and uploads with retry + smaller
batch size to be resilient.

Usage:
  docker compose exec app python scripts/reupload_to_server.py douglas.lv
  docker compose exec app python scripts/reupload_to_server.py notino.lv --batch 30

Required env:
  SERVER_URL    Same as scrape_worker.py (default http://46.101.174.12:8000)
  WORKER_TOKEN  Same shared secret
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx
from loguru import logger
from sqlalchemy import select

from app.core.database import async_session_maker
from app.domain.models import Product


SERVER_URL = os.getenv("SERVER_URL", "http://46.101.174.12:8000").rstrip("/")
WORKER_TOKEN = os.getenv("WORKER_TOKEN")
DEFAULT_BATCH = 50  # smaller than scrape_worker's 100 — less likely to time out


async def fetch_products(domain: str) -> list[dict[str, Any]]:
    """Read all products matching the domain from local DB."""
    async with async_session_maker() as session:
        stmt = select(Product).where(Product.url.contains(domain))
        rows = (await session.execute(stmt)).scalars().all()

    products = []
    for p in rows:
        products.append({
            "url": p.url,
            "title": p.title,
            "brand": p.brand,
            "volume": p.volume,
            "concentration": p.concentration,
            "image_url": p.image_url,
            "last_price": float(p.last_price) if p.last_price is not None else None,
            "is_available": bool(p.is_available),
        })
    return products


async def upload_batch(client: httpx.AsyncClient, domain: str, batch: list[dict], attempt: int = 1) -> dict:
    """POST one batch with retry on HTTP errors. Returns server response or raises."""
    payload = {"job_id": f"reupload-{domain}", "domain": domain, "products": batch}
    headers = {"Authorization": f"Bearer {WORKER_TOKEN}"}
    try:
        r = await client.post(
            f"{SERVER_URL}/api/admin/scrape/ingest",
            json=payload, headers=headers, timeout=90.0,
        )
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        if attempt < 4:
            wait = 2 ** attempt  # 2s, 4s, 8s
            logger.warning(f"Batch failed (attempt {attempt}/{4}): {e} — retrying in {wait}s")
            await asyncio.sleep(wait)
            return await upload_batch(client, domain, batch, attempt + 1)
        raise


async def main(domain: str, batch_size: int) -> None:
    if not WORKER_TOKEN:
        logger.error("WORKER_TOKEN env var is required")
        sys.exit(1)

    logger.info(f"📥 Reading local DB for products with url containing '{domain}'…")
    products = await fetch_products(domain)
    logger.info(f"📦 Found {len(products)} products to re-upload")

    if not products:
        logger.warning("Nothing to upload — exiting")
        return

    totals = {"inserted": 0, "updated": 0, "price_changes": 0}
    failed_batches = 0

    async with httpx.AsyncClient() as client:
        for i in range(0, len(products), batch_size):
            batch = products[i : i + batch_size]
            try:
                res = await upload_batch(client, domain, batch)
                for k in totals:
                    totals[k] += int(res.get(k, 0))
                logger.info(
                    f"✅ Batch {i // batch_size + 1}: {len(batch)} → "
                    f"+{res.get('inserted', 0)} new, ~{res.get('updated', 0)} updated, "
                    f"Δ{res.get('price_changes', 0)} prices"
                )
            except Exception as e:
                failed_batches += 1
                logger.error(f"❌ Batch {i // batch_size + 1} permanently failed after retries: {e}")
                # Keep trying remaining batches instead of bailing entirely

    logger.info(
        f"🏁 Done. Totals: inserted={totals['inserted']}, updated={totals['updated']}, "
        f"price_changes={totals['price_changes']}, failed_batches={failed_batches}"
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("domain", help="Domain substring to match against product.url (e.g. douglas.lv)")
    ap.add_argument("--batch", type=int, default=DEFAULT_BATCH, help=f"Batch size (default {DEFAULT_BATCH})")
    args = ap.parse_args()

    logger.info(f"Target server: {SERVER_URL}")
    asyncio.run(main(args.domain, args.batch))
