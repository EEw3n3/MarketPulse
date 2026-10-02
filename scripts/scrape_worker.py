"""Distributed scrape worker — runs on the user's local machine.

Long-polls the production server for scrape jobs. When a job arrives, runs
the scrape locally (Playwright with residential IP bypasses Cloudflare),
writes results to the LOCAL docker DB, then POSTs the freshly-touched
products to the server's ingest endpoint.

Flow:
  1. POLL  server `GET /admin/scrape/poll` (long-poll, 25s)
  2. SCRAPE  scraper_service runs against local DB (writes products + history)
  3. SELECT  pull products whose last_seen > job_start_time AND search_term = domain
  4. POST    batches to `/admin/scrape/ingest`
  5. COMPLETE `POST /admin/scrape/complete?job_id=...&status=done`

Required env:
  WORKER_TOKEN     Shared secret (same value on server's .env)
  SERVER_URL       Base URL of the production API, e.g. http://46.101.174.12:8000

Optional:
  POLL_TIMEOUT     Long-poll seconds (default 25)
  BATCH_SIZE       Products per ingest POST (default 100)
  LOG_LEVEL        DEBUG / INFO / WARNING (default INFO)

Usage:
  docker compose exec app python scripts/scrape_worker.py
  # Or local (without docker), with poetry/venv:
  python scripts/scrape_worker.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx
from loguru import logger
from sqlalchemy import select

from app.core.database import async_session_maker
from app.core.registry import register_domain
from app.domain.models import Product
from app.main import process_target_worker


SERVER_URL = os.getenv("SERVER_URL", "http://46.101.174.12:8000").rstrip("/")
WORKER_TOKEN = os.getenv("WORKER_TOKEN")
POLL_TIMEOUT = int(os.getenv("POLL_TIMEOUT", "25"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))
CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "5"))
DEFAULT_MAX_ITEMS = int(os.getenv("DEFAULT_MAX_ITEMS", "9999"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

logger.remove()
logger.add(sys.stderr, level=LOG_LEVEL, format="{time:HH:mm:ss} | {level: <7} | {message}")


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {WORKER_TOKEN}"}


def _target_for_domain(domain: str) -> Optional[dict]:
    """Load the categories.json entry whose URL contains `domain`."""
    cfg_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "configs", "categories.json"))
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cats = json.load(f)
    except Exception as e:
        logger.error(f"Cannot read categories.json: {e}")
        return None
    for category_block in cats.values():
        for target in category_block.get("targets", []):
            if domain in target.get("url", ""):
                return target
    return None


async def run_scrape(domain: str, max_items: int) -> Optional[float]:
    """Run a full local scrape for `domain` with a cap of `max_items` products.
    Returns the job start timestamp (so we can later select products touched
    after this) or None on failure."""
    target = _target_for_domain(domain)
    if not target:
        logger.error(f"Domain {domain} not found in configs/categories.json")
        return None

    from urllib.parse import urlparse
    site_name = target.get("site") or urlparse(target["url"]).netloc
    register_domain(target["url"])

    target_payload = {
        "url": target["url"],
        "search_term": "WorkerScrape",
        "category": target.get("category", "Men's Perfume"),
        "site_name": site_name,
    }

    started = time.time()
    logger.info(f"🔍 Starting local scrape: {domain} (max_items={max_items})")
    try:
        await process_target_worker(target_payload, None, None, enable_price_filter=True, max_items=max_items)
    except Exception as e:
        logger.exception(f"Scrape failed for {domain}: {e}")
        return None
    elapsed = time.time() - started
    logger.info(f"✅ Local scrape finished for {domain} in {elapsed:.1f}s")
    return started


async def fetch_fresh_products(domain: str, since_ts: float) -> list[dict]:
    """Read products from LOCAL DB whose last_seen ≥ since_ts and whose URL
    belongs to this domain. Returns ingest-ready dicts."""
    since_dt = datetime.utcfromtimestamp(since_ts)
    async with async_session_maker() as session:
        stmt = select(Product).where(
            Product.last_seen >= since_dt,
            Product.url.contains(domain),
        )
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
            "card_type": p.card_type,
            "promo_price": float(p.promo_price) if p.promo_price is not None else None,
            "promo_code": p.promo_code,
        })
    return products


async def push_to_server(client: httpx.AsyncClient, job_id: str, domain: str, products: list[dict]) -> dict:
    """Batch-POST products to /admin/scrape/ingest."""
    totals = {"inserted": 0, "updated": 0, "price_changes": 0}
    for i in range(0, len(products), BATCH_SIZE):
        batch = products[i : i + BATCH_SIZE]
        payload = {"job_id": job_id, "domain": domain, "products": batch}
        try:
            r = await client.post(
                f"{SERVER_URL}/api/admin/scrape/ingest",
                json=payload, headers=_auth_headers(), timeout=60.0,
            )
            r.raise_for_status()
            res = r.json()
            for k in totals:
                totals[k] += int(res.get(k, 0))
            logger.info(f"📤 Batch {i // BATCH_SIZE + 1}: {len(batch)} → +{res.get('inserted', 0)} new, "
                        f"~{res.get('updated', 0)} updated, Δ{res.get('price_changes', 0)} prices")
        except httpx.HTTPError as e:
            logger.error(f"Ingest batch failed (offset {i}): {e}")
            raise
    return totals


async def mark_complete(client: httpx.AsyncClient, job_id: str, status: str) -> None:
    try:
        await client.post(
            f"{SERVER_URL}/api/admin/scrape/complete",
            params={"job_id": job_id, "status": status},
            headers=_auth_headers(), timeout=10.0,
        )
    except httpx.HTTPError as e:
        logger.warning(f"Could not mark complete: {e}")


async def handle_job(
    sem: asyncio.Semaphore,
    client: httpx.AsyncClient,
    job: dict,
) -> None:
    """End-to-end processing of one job: scrape → fetch fresh → ingest → mark.

    Bounded by `sem` so concurrent jobs don't exceed WORKER_CONCURRENCY.
    """
    async with sem:
        job_id = job["id"]
        domain = job["domain"]
        max_items = job.get("max_items") or DEFAULT_MAX_ITEMS
        logger.info(f"📦 Received job {job_id} → {domain} (limit={max_items})")

        since = await run_scrape(domain, max_items)
        if since is None:
            await mark_complete(client, job_id, "failed")
            return

        products = await fetch_fresh_products(domain, since)
        if not products:
            logger.warning(f"No fresh products to upload for {domain}")
            await mark_complete(client, job_id, "done")
            return

        logger.info(f"📤 Uploading {len(products)} products to server for {domain}")
        try:
            totals = await push_to_server(client, job_id, domain, products)
            logger.info(
                f"✅ Job {job_id} ({domain}) complete — inserted={totals['inserted']}  "
                f"updated={totals['updated']}  price_changes={totals['price_changes']}"
            )
            await mark_complete(client, job_id, "done")
        except Exception:
            await mark_complete(client, job_id, "failed")


async def worker_loop() -> None:
    if not WORKER_TOKEN:
        logger.error("WORKER_TOKEN env var is required. Set it and re-run.")
        sys.exit(1)

    logger.info(
        f"🤖 Worker started — server={SERVER_URL}  poll={POLL_TIMEOUT}s  "
        f"batch={BATCH_SIZE}  concurrency={CONCURRENCY}"
    )
    sem = asyncio.Semaphore(CONCURRENCY)
    pending: set[asyncio.Task] = set()

    async with httpx.AsyncClient() as client:
        while True:
            # Reap finished tasks
            done = {t for t in pending if t.done()}
            pending -= done
            for t in done:
                exc = t.exception()
                if exc:
                    logger.error(f"Job task crashed: {exc!r}")

            try:
                resp = await client.get(
                    f"{SERVER_URL}/api/admin/scrape/poll",
                    params={"timeout": POLL_TIMEOUT},
                    headers=_auth_headers(),
                    timeout=POLL_TIMEOUT + 10,
                )
                resp.raise_for_status()
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                logger.warning(f"Poll failed: {e} — retrying in 10s")
                await asyncio.sleep(10)
                continue

            job = resp.json().get("job")
            if not job:
                # No job ready, just loop and poll again
                continue

            # Spawn job processing in its own task — caps at CONCURRENCY via the
            # semaphore inside handle_job. Polling continues immediately so 5
            # jobs in queue all start almost simultaneously.
            task = asyncio.create_task(handle_job(sem, client, job))
            pending.add(task)


def main() -> None:
    try:
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        logger.info("👋 Worker stopped by user")


if __name__ == "__main__":
    main()
