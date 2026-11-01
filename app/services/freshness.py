"""What "in stock" and "a deal" mean on the site.

A shop drops a sold-out or discontinued bottle from its catalogue. The scraper
walks the catalogue, so it never visits that bottle again, and without this
module the bottle would stay "in stock" at its old price forever (31.10: 1 747
such rows, the top card of Today among them).

- Every pass over a shop's catalogue is a ScrapeRun. A run is complete when it
  ended without an error and saw at least COMPLETE_SHARE of what a usual run of
  that shop sees.
- After a complete run, the sweep marks unavailable every product of the shop
  that was not seen in this run nor in the previous complete one: two misses in
  a row, so one odd pass cannot switch a product off.
- A deal (Today, the landing teaser, analytics moves) needs a price read in the
  last DEAL_MAX_AGE: Notino and 220.lv come from the PC, and when the PC skips a
  night their prices are a day old or more.

Recording never breaks a scrape: every function logs and carries on when the
table is missing or the database refuses.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from statistics import median
from typing import Optional
from urllib.parse import urlparse

from loguru import logger
from sqlalchemy import func, select, text

from app.core.database import async_session_maker
from app.domain.models import Product, ScrapeRun

DEAL_MAX_AGE = timedelta(hours=30)
# A run that saw less than this share of a usual run is not complete.
COMPLETE_SHARE = 0.9
# "A usual run" = the median of the shop's last complete runs.
BASELINE_RUNS = 5
# Without earlier runs, the usual catalogue is what was seen in this window.
FIRST_RUN_WINDOW = timedelta(days=3)
# Never switch off more than this share of a shop's in-stock products at once:
# that is a broken pass or a changed URL scheme, not a sell-out.
MAX_SWEEP_SHARE = 0.3


def shop_of(url: str) -> str:
    """"https://www.notino.lv/..." -> "notino.lv" (the form Product.search_term uses)."""
    return (urlparse(url or "").hostname or "").lower().removeprefix("www.")


def deal_fresh_since(now: Optional[datetime] = None) -> datetime:
    """Oldest last_seen a listing may have to count as a deal."""
    return (now or datetime.utcnow()) - DEAL_MAX_AGE


async def start_run(shop: str, source: str = "server", job_id: Optional[str] = None) -> Optional[int]:
    """Record the start of a pass over `shop`. Returns the run id, or None."""
    if not shop:
        return None
    try:
        async with async_session_maker() as session:
            run = ScrapeRun(shop=shop, source=source, job_id=job_id, started_at=datetime.utcnow())
            session.add(run)
            await session.commit()
            return run.id
    except Exception as e:
        logger.warning(f"Scrape run of {shop} not recorded: {e}")
        return None


async def worker_run(job_id: str, shop: str) -> Optional[int]:
    """The run of a PC worker job. Its first upload batch creates it, so every
    product of the job is stamped (last_seen) after the run's start."""
    try:
        async with async_session_maker() as session:
            run_id = await session.scalar(select(ScrapeRun.id).where(ScrapeRun.job_id == job_id).limit(1))
        if run_id:
            return run_id
    except Exception as e:
        logger.warning(f"Scrape run of job {job_id} not found: {e}")
        return None
    return await start_run(shop, "worker", job_id)


async def run_for_job(job_id: str) -> Optional[int]:
    try:
        async with async_session_maker() as session:
            return await session.scalar(select(ScrapeRun.id).where(ScrapeRun.job_id == job_id).limit(1))
    except Exception as e:
        logger.warning(f"Scrape run of job {job_id} not found: {e}")
        return None


async def finish_run(run_id: Optional[int], ok: bool, note: Optional[str] = None) -> Optional[ScrapeRun]:
    """Close a run: count what it saw, decide whether it is complete and, when
    it is, sweep the products the shop stopped listing."""
    if not run_id:
        return None
    try:
        async with async_session_maker() as session:
            run = await session.get(ScrapeRun, run_id)
            if run is None or run.status != "running":
                return run
            now = datetime.utcnow()
            run.items_seen = int(await session.scalar(
                select(func.count(Product.id)).where(
                    Product.search_term == run.shop, Product.last_seen >= run.started_at,
                )
            ) or 0)
            run.finished_at = now
            run.status = "done" if ok else "failed"

            earlier = (await session.execute(
                select(ScrapeRun)
                .where(ScrapeRun.shop == run.shop, ScrapeRun.complete.is_(True),
                       ScrapeRun.id != run.id, ScrapeRun.started_at < run.started_at)
                .order_by(ScrapeRun.started_at.desc())
                .limit(BASELINE_RUNS)
            )).scalars().all()
            if earlier:
                usual = median(r.items_seen for r in earlier)
            else:
                usual = int(await session.scalar(
                    select(func.count(Product.id)).where(
                        Product.search_term == run.shop,
                        Product.last_seen >= run.started_at - FIRST_RUN_WINDOW,
                    )
                ) or 0)
            run.complete = bool(ok and run.items_seen > 0 and run.items_seen >= COMPLETE_SHARE * usual)
            notes = [note] if note else []
            if ok and not run.complete:
                notes.append(f"incomplete: saw {run.items_seen} of a usual {int(usual)}")

            if run.complete and earlier:
                swept, why = await _sweep(session, run.shop, cutoff=earlier[0].started_at, now=now)
                run.swept = swept
                if why:
                    notes.append(why)
            run.note = "; ".join(notes)[:255] or None
            session.add(run)
            await session.commit()
            logger.info(
                f"Scrape run {run.id} {run.shop}: {run.status}, saw {run.items_seen}"
                f" (usual {int(usual)}), complete={run.complete}, swept {run.swept}"
                + (f" — {run.note}" if run.note else "")
            )
            return run
    except Exception as e:
        logger.warning(f"Scrape run {run_id} not closed: {e}")
        return None


async def _sweep(session, shop: str, cutoff: datetime, now: datetime) -> tuple[int, Optional[str]]:
    """Mark unavailable the shop's products not seen since `cutoff` (the start
    of the previous complete run). Writes an out_of_stock history row for each,
    so the price chart shows where the listing ended."""
    params = {"shop": shop, "cutoff": cutoff, "now": now}
    stale = int(await session.scalar(text(
        "select count(*) from product where search_term = :shop and is_available and last_seen < :cutoff"
    ), params) or 0)
    if not stale:
        return 0, None
    in_stock = int(await session.scalar(text(
        "select count(*) from product where search_term = :shop and is_available"
    ), params) or 0)
    if stale > MAX_SWEEP_SHARE * in_stock:
        return 0, f"sweep skipped: {stale} of {in_stock} in-stock products unseen, over {int(MAX_SWEEP_SHARE * 100)}%"
    await session.execute(text("""
        insert into pricehistory (price, in_stock, parsed_at, change_type, product_id)
        select last_price, false, :now, 'out_of_stock', id from product
        where search_term = :shop and is_available and last_seen < :cutoff and last_price > 0
    """), params)
    await session.execute(text(
        "update product set is_available = false where search_term = :shop and is_available and last_seen < :cutoff"
    ), params)
    return stale, None


async def last_runs(limit: int = 30) -> list[ScrapeRun]:
    """Latest runs of every shop, newest first (admin panel)."""
    async with async_session_maker() as session:
        return list((await session.execute(
            select(ScrapeRun).order_by(ScrapeRun.started_at.desc()).limit(limit)
        )).scalars().all())
