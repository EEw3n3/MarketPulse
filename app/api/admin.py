"""Admin-only API endpoints. All routes require is_admin=True via get_current_admin."""
import json
import os
import re
import time
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Literal, Optional, List
from urllib.parse import urlparse

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, delete, update, or_

from app.api.deps import get_db, get_current_admin, get_worker
from app.api.schemas import DupGroup, DupOffer, DupPage, DupPair
from app.core.job_queue import job_queue
from app.domain.models import User, ScrapingRule, Product, PriceHistory, Favorite, UserPreferences, PlanChange, GroupPair
from app.services import billing, group_merge, plans
from app.services.normalizer import is_placeholder_brand

router = APIRouter(prefix="/admin", tags=["admin"])

# ── In-memory rate limiters ───────────────────────────────────────────────────

_last_scrape: dict[str, float] = {}
_last_regen: dict[str, float] = {}
SCRAPE_COOLDOWN_S = 30    # 30s between scrapes per domain (demo-friendly)
REGEN_COOLDOWN_S = 3600   # 1 hour between AI regenerations per domain

# ── Pydantic models ───────────────────────────────────────────────────────────

class SiteHealth(BaseModel):
    domain: str
    site_name: str
    last_scrape_at: Optional[datetime]
    product_count: int
    health_score: float
    success_count: int
    failure_count: int
    last_error: Optional[str]

class HealthResponse(BaseModel):
    sites: List[SiteHealth]
    db_latency_ms: float
    total_products: int
    total_users: int

class ScrapingRuleRead(BaseModel):
    domain: str
    site_name: str
    container_css: str
    title_css: str
    price_css: Optional[str]
    image_css: Optional[str]
    brand_css: Optional[str]
    concentration_css: Optional[str]
    stock_css: Optional[str]
    next_page_css: Optional[str]
    health_score: float
    success_count: int
    failure_count: int
    last_success: Optional[datetime]
    last_error: Optional[str]

class ScrapeRunRead(BaseModel):
    shop: str
    source: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: str
    items_seen: int
    complete: bool
    swept: int
    note: Optional[str] = None


class ShopFreshness(BaseModel):
    shop: str
    in_stock: int
    stale_in_stock: int          # in stock but not seen for 30 hours
    last_seen: Optional[datetime] = None
    checks_7d: int = 0           # product-page checks in 7 days
    matched_7d: int = 0
    corrected_7d: int = 0
    unreadable_7d: int = 0


class PageMismatch(BaseModel):
    product_id: Optional[int] = None
    shop: str
    kind: str
    title: Optional[str] = None
    volume: Optional[str] = None
    url: Optional[str] = None
    checked_at: datetime
    db_price: Optional[float] = None
    page_price: Optional[float] = None
    db_in_stock: Optional[bool] = None
    page_in_stock: Optional[bool] = None
    note: Optional[str] = None


class DataQualityResponse(BaseModel):
    total_products: int
    products_without_image: int
    products_without_history: int
    products_ungrouped: int
    total_price_events: int
    shops: List[ShopFreshness] = []
    runs: List[ScrapeRunRead] = []
    mismatches: List[PageMismatch] = []

class AdminUserRead(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    is_active: bool
    is_admin: bool
    plan: str = "free"
    is_pro: bool = False               # Pro features open (admin, or a running term)
    pro_until: Optional[datetime] = None  # UTC; None with plan "pro" = no end
    pro_source: Optional[str] = None   # "admin" | "payment"
    created_at: datetime
    favorites_count: int = 0

class AdminUsersPage(BaseModel):
    items: List[AdminUserRead]
    total: int
    page: int
    page_size: int

class AdminUserPatch(BaseModel):
    """`plan="free"` takes Pro away. Pro is given with one of: `pro_days`
    (counted from the current end while Pro runs), `pro_until` (a date, Pro
    to the end of that day in Riga), `pro_forever`; `plan="pro"` alone = no end."""
    is_active: Optional[bool] = None
    plan: Optional[Literal["free", "pro"]] = None
    pro_days: Optional[int] = None
    pro_until: Optional[date] = None
    pro_forever: bool = False
    note: Optional[str] = None

class PlanChangeRead(BaseModel):
    at: datetime
    action: str
    plan: str
    pro_until: Optional[datetime]
    source: Optional[str]
    note: Optional[str]
    by_email: Optional[str] = None

class LogsResponse(BaseModel):
    lines: List[str]
    total: int

# ── In-memory log ring buffer (populated by logging handler in main.py) ───────

LOG_RING: list[str] = []
MAX_RING_SIZE = 500


def push_log(line: str) -> None:
    """Called by the log handler to append to the ring buffer."""
    if len(LOG_RING) >= MAX_RING_SIZE:
        LOG_RING.pop(0)
    LOG_RING.append(line)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def admin_health(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """System health: per-site scraping stats, DB latency, total counts."""
    t0 = time.monotonic()
    total_products = await db.scalar(select(func.count(Product.id))) or 0
    total_users = await db.scalar(select(func.count(User.id))) or 0
    db_latency = round((time.monotonic() - t0) * 1000, 2)

    # Single-query aggregation across all distinct search_term values, then
    # normalized matching to ScrapingRule. Historic data wrote search_term as
    # "notino"/"notino.lv"/"Douglas Latvia" inconsistently, so a strict equality
    # vs rule.domain ("notino.lv") would return 0 for half the data.
    counts_stmt = select(Product.search_term, func.count(Product.id)).group_by(Product.search_term)
    counts_rows = (await db.execute(counts_stmt)).all()

    def _norm(s: str | None) -> str:
        return (s or "").lower().replace(".lv", "").replace(" latvia", "").strip()

    counts_by_norm: dict[str, int] = {}
    for st, cnt in counts_rows:
        norm = _norm(st)
        if not norm:
            continue
        counts_by_norm[norm] = counts_by_norm.get(norm, 0) + cnt

    rules_result = await db.execute(select(ScrapingRule))
    rules = rules_result.scalars().all()

    sites = []
    for rule in rules:
        # Match by normalized domain OR site_name — both can appear in legacy data
        pc = counts_by_norm.get(_norm(rule.domain), 0) or counts_by_norm.get(_norm(rule.site_name), 0)
        sites.append(SiteHealth(
            domain=rule.domain,
            site_name=rule.site_name,
            last_scrape_at=rule.last_success,
            product_count=pc,
            health_score=rule.health_score,
            success_count=rule.success_count,
            failure_count=rule.failure_count,
            last_error=rule.last_error,
        ))

    return HealthResponse(
        sites=sites,
        db_latency_ms=db_latency,
        total_products=total_products,
        total_users=total_users,
    )


@router.get("/rules/{domain}", response_model=ScrapingRuleRead)
async def get_rules(
    domain: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """CSS selector rules for a specific domain."""
    rule = await db.scalar(select(ScrapingRule).where(ScrapingRule.domain == domain))
    if not rule:
        raise HTTPException(status_code=404, detail=f"No rules for domain '{domain}'")
    return ScrapingRuleRead.model_validate(rule, from_attributes=True)


@router.post("/rules/{domain}/regenerate")
async def regenerate_rules(
    domain: str,
    _: User = Depends(get_current_admin),
):
    """Trigger AI rule regeneration for a domain (rate-limited to once per hour)."""
    now = time.time()
    if domain in _last_regen and now - _last_regen[domain] < REGEN_COOLDOWN_S:
        remaining = int(REGEN_COOLDOWN_S - (now - _last_regen[domain]))
        raise HTTPException(status_code=429, detail=f"Rate limit: retry in {remaining}s")
    _last_regen[domain] = now
    # Phase 4 TODO: trigger ai_generator.regenerate_rules(domain) as background task
    return {"status": "queued", "domain": domain}


# ── Distributed scrape worker endpoints ──────────────────────────────────────
# IMPORTANT: these MUST be declared before `POST /scrape/{domain}` because
# FastAPI matches routes in declaration order — `/scrape/{domain}` (POST)
# would otherwise shadow `/scrape/ingest`, `/scrape/complete` etc and force
# the wrong auth (admin JWT) on what should be worker-only endpoints.


@router.get("/scrape/poll")
async def scrape_poll(
    timeout: int = Query(25, ge=1, le=55),
    _: bool = Depends(get_worker),
):
    """Worker long-poll: BLPOP a scrape job from the Redis queue.

    Returns the job (`{id, domain}`) when one is available, or 204 after
    `timeout` seconds with no job. Also refreshes the worker heartbeat so the
    admin panel can show 'Worker online'.
    """
    await job_queue.heartbeat()
    job = await job_queue.dequeue(timeout_s=timeout)
    if not job:
        return {"job": None}
    return {
        "job": {
            "id": job["id"],
            "domain": job["domain"],
            "max_items": job.get("max_items"),
        }
    }


class IngestProductIn(BaseModel):
    url: str
    title: str
    brand: Optional[str] = None
    volume: Optional[str] = None
    concentration: Optional[str] = None
    image_url: Optional[str] = None
    last_price: Optional[float] = None
    is_available: bool = True
    card_type: str = "perfume"  # "perfume" | "gift_set"
    promo_price: Optional[float] = None  # price with a shop promo code
    promo_code: Optional[str] = None


class IngestBatchIn(BaseModel):
    job_id: str
    domain: str
    products: List[IngestProductIn]


@lru_cache(maxsize=1)
def _shop_domains() -> frozenset[str]:
    """Shop hosts from configs/categories.json, without "www."."""
    path = os.path.join(os.path.dirname(__file__), "..", "..", "configs", "categories.json")
    with open(path, "r", encoding="utf-8") as f:
        cats = json.load(f)
    return frozenset(
        (urlparse(t["url"]).hostname or "").lower().removeprefix("www.")
        for block in cats.values() for t in block.get("targets", [])
    )


@router.post("/scrape/ingest")
async def scrape_ingest(
    payload: IngestBatchIn,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(get_worker),
):
    """Worker uploads scraped products in batches.

    Upserts by URL: existing product → update price/title/last_seen + emit
    PriceHistory if price changed; new product → insert + run matcher to
    assign group_id + emit 'initial' PriceHistory.
    """
    from decimal import Decimal
    from app.core.constants import MAX_PLAUSIBLE_PRICE
    from app.services.matcher import matcher_service
    from app.domain.models import ProductGroup
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    shop = payload.domain.lower().removeprefix("www.")
    if shop not in _shop_domains():
        raise HTTPException(status_code=400, detail=f"Unknown shop domain: {payload.domain}")
    # The job's pass over the shop starts with its first batch (see
    # app/services/freshness.py); /scrape/complete closes it.
    from app.services import freshness
    await freshness.worker_run(payload.job_id, shop)

    inserted = 0
    updated = 0
    price_changes = 0
    skipped = 0

    for item in payload.products:
        # A leaked worker token must not be able to plant foreign links
        # (javascript: in "Buy" buttons) or internal image URLs.
        host = (urlparse(item.url).hostname or "").lower()
        if not item.url.startswith("https://") or not (host == shop or host.endswith("." + shop)):
            skipped += 1
            continue
        if item.image_url and not item.image_url.startswith("https://"):
            item.image_url = None
        if is_placeholder_brand(item.brand):  # a 220.lv seller's "Nav norādīts"
            item.brand = None
        # Tolerate accidental duplicates by URL+volume (race condition leftovers
        # from earlier parallel uploads created some). `scalar_one_or_none()`
        # crashes on >1 row; we just take the first match — subsequent ingests
        # will overwrite it cleanly.
        stmt = (
            select(Product)
            .where(Product.url == item.url, Product.volume == item.volume)
            .order_by(Product.id)
            .limit(1)
        )
        product = (await db.execute(stmt)).scalar_one_or_none()
        if product is None and "notino.lv/" in item.url:
            # Notino links a card to one of its variants (".../p-16228733/") and
            # picks a different one from run to run; the page without the
            # /p-…/ part + volume is the same variant.
            base = re.sub(r"p-\d+/?$", "", item.url)
            legacy = (
                select(Product)
                .where(
                    Product.search_term == "notino.lv",
                    Product.volume == item.volume,
                    or_(Product.url == base, Product.url.like(base + "p-%")),
                )
                .order_by(Product.last_seen.desc())
                .limit(1)
            )
            product = (await db.execute(legacy)).scalar_one_or_none()
            if product is not None:
                product.url = item.url
        price_dec =Decimal(str(item.last_price)) if item.last_price is not None else None
        if price_dec is not None and price_dec > MAX_PLAUSIBLE_PRICE:
            price_dec = None  # a seller's placeholder price, not a real one
        promo_dec = Decimal(str(item.promo_price)) if item.promo_price is not None else None

        if product is None:
            # Resolve group_id via matcher (gift sets never join a chain)
            match = None
            if item.card_type == "perfume":
                match = await matcher_service.find_best_match(
                    db,
                    {"title": item.title, "brand": item.brand, "volume": item.volume, "concentration": item.concentration},
                )
            if item.card_type != "perfume":
                group_id = None
            elif match:
                group_id = match.id
            else:
                canonical = matcher_service.get_canonical_name(
                    item.title, brand=item.brand, concentration=item.concentration
                )
                upsert = pg_insert(ProductGroup).values(
                    name=canonical, category="Perfume", created_at=datetime.utcnow()
                ).on_conflict_do_nothing(index_elements=["name"])
                await db.execute(upsert)
                await db.flush()
                resolved = (await db.execute(select(ProductGroup).where(ProductGroup.name == canonical))).scalar_one()
                group_id = (await matcher_service.resolve_merged(db, resolved)).id

            product = Product(
                url=item.url,
                title=item.title,
                brand=item.brand,
                volume=item.volume,
                concentration=item.concentration,
                image_url=item.image_url,
                search_term=shop,
                last_price=price_dec,
                is_available=item.is_available,
                last_seen=datetime.utcnow(),
                group_id=group_id,
                card_type=item.card_type,
                promo_price=promo_dec,
                promo_code=item.promo_code,
            )
            db.add(product)
            await db.flush()
            if price_dec is not None and price_dec > 0:
                db.add(PriceHistory(
                    product_id=product.id, price=price_dec,
                    in_stock=item.is_available, change_type="initial",
                ))
            inserted += 1
        else:
            updated += 1
            product.title = item.title
            product.brand = item.brand or (None if is_placeholder_brand(product.brand) else product.brand)
            product.volume = item.volume or product.volume
            product.concentration = item.concentration or product.concentration
            if item.image_url:
                product.image_url = item.image_url
            was_available = product.is_available
            product.is_available = item.is_available
            product.last_seen = datetime.utcnow()
            product.card_type = item.card_type
            if item.card_type != "perfume":
                product.group_id = None
            product.promo_price = promo_dec
            product.promo_code = item.promo_code

            # Same change types as the server-side scraper (_flush_candidates):
            # a stock change wins over a price change, so the price chart
            # shows where a shop ran out and where it came back.
            change = None
            has_price = price_dec is not None and price_dec > 0
            old = product.last_price
            if has_price and old != price_dec:
                if old is not None and old > 0 and price_dec < old:
                    change = "price_down"
                elif old is not None and old > 0 and price_dec > old:
                    change = "price_up"
                else:
                    change = "initial"
                product.old_price = old
                product.last_price = price_dec
                price_changes += 1
            if item.is_available and not was_available and has_price:
                change = "back_in_stock"
            elif not item.is_available and was_available:
                change = "out_of_stock"
            history_price = price_dec if has_price else product.last_price
            if change and history_price and history_price > 0:
                db.add(PriceHistory(
                    product_id=product.id, price=history_price,
                    in_stock=item.is_available, change_type=change,
                ))

    await db.commit()
    if skipped:
        logger.warning(f"Ingest {payload.domain}: skipped {skipped} products with foreign or non-https URLs")
    return {"inserted": inserted, "updated": updated, "price_changes": price_changes, "skipped": skipped}


class PageCheckIn(BaseModel):
    url: str
    volume: Optional[str] = None
    kind: Literal["deal", "random"] = "deal"
    checked_at: datetime
    db_price: Optional[float] = None
    page_price: Optional[float] = None
    db_in_stock: Optional[bool] = None
    page_in_stock: Optional[bool] = None
    ok: Optional[bool] = None
    note: Optional[str] = None


class PageCheckBatchIn(BaseModel):
    job_id: str
    domain: str
    checks: List[PageCheckIn]


@router.get("/scrape/deal-candidates")
async def scrape_deal_candidates(
    domain: str,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(get_worker),
):
    """The listings of a shop that would be on Today once their product page
    confirms them. The PC worker reads these pages after uploading a pass:
    the PC's own database holds other history, so its own candidates would
    not be the ones the site shows."""
    from app.services import page_check

    shop = domain.lower().removeprefix("www.")
    if shop not in _shop_domains():
        raise HTTPException(status_code=400, detail=f"Unknown shop domain: {domain}")
    return [{"url": p.url, "volume": p.volume} for p in await page_check.deal_candidates(db, shop)]


@router.post("/scrape/page-checks")
async def scrape_page_checks(
    payload: PageCheckBatchIn,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(get_worker),
):
    """Worker uploads the product-page checks of a job, after its products.

    The products themselves (corrected to the page where it disagreed) came
    with /scrape/ingest; this stores the check and stamps the listing, so a
    confirmed deal can be shown (app/services/page_check.py)."""
    from decimal import Decimal
    from app.domain.models import PageCheck

    shop = payload.domain.lower().removeprefix("www.")
    if shop not in _shop_domains():
        raise HTTPException(status_code=400, detail=f"Unknown shop domain: {payload.domain}")
    stored = 0
    for c in payload.checks:
        q = select(Product).where(Product.url == c.url, Product.search_term == shop)
        q = q.where(Product.volume == c.volume) if c.volume else q.where(Product.volume.is_(None))
        product = (await db.execute(q.order_by(Product.id).limit(1))).scalar_one_or_none()
        if product is None:
            continue
        checked_at = c.checked_at.replace(tzinfo=None)
        dec = lambda v: Decimal(str(v)).quantize(Decimal("0.01")) if v is not None else None  # noqa: E731
        db.add(PageCheck(
            product_id=product.id, shop=shop, kind=c.kind, checked_at=checked_at,
            db_price=dec(c.db_price), page_price=dec(c.page_price), db_in_stock=c.db_in_stock,
            page_in_stock=c.page_in_stock, ok=c.ok, note=(c.note or "")[:255] or None,
        ))
        if c.page_price is not None and (product.page_checked_at is None or checked_at > product.page_checked_at):
            product.page_checked_at = checked_at
            product.page_price = dec(c.page_price)
        stored += 1
    await db.commit()
    return {"stored": stored}


@router.post("/scrape/complete")
async def scrape_complete(
    job_id: str = Query(...),
    status: str = Query("done", pattern="^(done|failed)$"),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(get_worker),
):
    """Worker marks a job done/failed so admin UI can reflect status.

    Also stamps the matching ScrapingRule's health fields on the SERVER's DB.
    The scrape itself runs on the local worker against its OWN database, so the
    rule-health updates inside scraper.py (last_success / success_count) only
    touch the worker's local rules — they never reach the server. Without this,
    the admin Health page's "LAST SCRAPE" date would never advance even after a
    fully successful scrape. The domain is resolved from the job state hash.
    """
    await job_queue.update_status(job_id, status)

    # Close the job's pass: a complete pass sweeps the products the shop no
    # longer lists (app/services/freshness.py).
    from app.services import freshness
    await freshness.finish_run(await freshness.run_for_job(job_id), status == "done")

    state = await job_queue.get_state(job_id)
    domain = (state or {}).get("domain")
    if domain:
        rule = await db.scalar(select(ScrapingRule).where(ScrapingRule.domain == domain))
        if rule:
            if status == "done":
                rule.last_success = datetime.utcnow()
                rule.success_count += 1
                rule.last_error = None
                # The worker's own data check ran on its DB; a finished job
                # clears the score left by an earlier failed server-side run.
                rule.health_score = 1.0
            else:
                rule.failure_count += 1
            await db.commit()

    return {"ok": True, "job_id": job_id, "status": status}


@router.get("/worker/status")
async def worker_status(_: User = Depends(get_current_admin)):
    """Admin UI badge — is the local worker online and how big is the queue?"""
    return await job_queue.worker_status()


# Declared AFTER the worker endpoints above (poll/ingest/complete) so the
# parametric `/scrape/{domain}` route doesn't shadow them in FastAPI's
# in-order route matching.
@router.post("/scrape/{domain}")
async def trigger_scrape(
    domain: str,
    max_items: Optional[int] = Query(None, ge=1, le=99999),
    _: User = Depends(get_current_admin),
):
    """Enqueue a scrape job for the distributed worker.

    Server-side Playwright doesn't work for Cloudflare-protected sites
    (notino.lv, 220.lv, etc), so the actual scraping is delegated to a local
    worker on the user's machine (residential IP). This endpoint just pushes
    a job to Redis; the worker long-polls /admin/scrape/poll and executes.

    `max_items` — optional cap on products to scrape. None = unlimited (worker
    defaults to 9999). Rate-limited to once per 5 min per domain.
    """
    now = time.time()
    if domain in _last_scrape and now - _last_scrape[domain] < SCRAPE_COOLDOWN_S:
        remaining = int(SCRAPE_COOLDOWN_S - (now - _last_scrape[domain]))
        raise HTTPException(status_code=429, detail=f"Rate limit: retry in {remaining}s")
    _last_scrape[domain] = now
    job_id = await job_queue.enqueue(domain, max_items=max_items)
    return {"status": "queued", "domain": domain, "job_id": job_id, "max_items": max_items}


@router.get("/scheduler/status")
async def get_scheduler_status(_: User = Depends(get_current_admin)):
    """APScheduler running state and next job run times."""
    from app.services.scheduler import scheduler_service
    return scheduler_service.get_status()


@router.get("/data-quality", response_model=DataQualityResponse)
async def data_quality(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Data quality metrics: missing images, missing history, ungrouped products."""
    total = await db.scalar(select(func.count(Product.id))) or 0
    no_image = await db.scalar(
        select(func.count(Product.id)).where(Product.image_url.is_(None))
    ) or 0

    products_with_history_subq = select(PriceHistory.product_id).distinct().subquery()
    no_history = await db.scalar(
        select(func.count(Product.id)).where(
            ~Product.id.in_(products_with_history_subq)
        )
    ) or 0

    ungrouped = await db.scalar(
        select(func.count(Product.id)).where(Product.group_id.is_(None))
    ) or 0

    total_events = await db.scalar(select(func.count(PriceHistory.id))) or 0

    return DataQualityResponse(
        total_products=total,
        products_without_image=no_image,
        products_without_history=no_history,
        products_ungrouped=ungrouped,
        total_price_events=total_events,
        **(await _freshness_report(db)),
    )


async def _freshness_report(db: AsyncSession) -> dict:
    """Per shop: stale "in stock" listings and the product-page checks of the
    last 7 days; the latest scrape runs; the latest listings the product page
    contradicted. Empty when the tables are not migrated yet."""
    from sqlalchemy import text as _text
    from app.domain.models import PageCheck, ScrapeRun
    from app.services.freshness import deal_fresh_since

    try:
        week = datetime.utcnow() - timedelta(days=7)
        fresh = deal_fresh_since()
        stock = (await db.execute(_text("""
            select search_term as shop,
                   count(*) filter (where is_available) as in_stock,
                   count(*) filter (where is_available and last_seen < :fresh) as stale,
                   max(last_seen) as last_seen
            from product group by search_term order by search_term
        """), {"fresh": fresh})).all()
        checks = {r.shop: r for r in (await db.execute(_text("""
            select shop, count(*) as n,
                   count(*) filter (where ok) as matched,
                   count(*) filter (where ok = false) as corrected,
                   count(*) filter (where ok is null) as unreadable
            from pagecheck where checked_at >= :week group by shop
        """), {"week": week})).all()}
        shops = []
        for r in stock:
            c = checks.get(r.shop)
            shops.append(ShopFreshness(
                shop=r.shop, in_stock=int(r.in_stock), stale_in_stock=int(r.stale), last_seen=r.last_seen,
                checks_7d=int(c.n) if c else 0, matched_7d=int(c.matched) if c else 0,
                corrected_7d=int(c.corrected) if c else 0, unreadable_7d=int(c.unreadable) if c else 0,
            ))
        runs = (await db.execute(select(ScrapeRun).order_by(ScrapeRun.started_at.desc()).limit(20))).scalars().all()
        bad = (await db.execute(
            select(PageCheck, Product.title, Product.volume, Product.url)
            .outerjoin(Product, Product.id == PageCheck.product_id)
            .where(PageCheck.ok.is_(False))
            .order_by(PageCheck.checked_at.desc()).limit(25)
        )).all()
    except Exception as e:
        logger.warning(f"freshness report unavailable: {e}")
        await db.rollback()
        return {}
    f = lambda v: float(v) if v is not None else None  # noqa: E731
    return {
        "shops": shops,
        "runs": [ScrapeRunRead(**{k: getattr(r, k) for k in ScrapeRunRead.model_fields}) for r in runs],
        "mismatches": [
            PageMismatch(product_id=c.product_id, shop=c.shop, kind=c.kind, title=title, volume=volume, url=url,
                         checked_at=c.checked_at, db_price=f(c.db_price), page_price=f(c.page_price),
                         db_in_stock=c.db_in_stock, page_in_stock=c.page_in_stock, note=c.note)
            for c, title, volume, url in bad
        ],
    }


def _admin_user(u: User, favorites: int) -> AdminUserRead:
    return AdminUserRead(
        id=u.id, email=u.email, full_name=u.full_name, is_active=u.is_active, is_admin=u.is_admin,
        plan=u.plan, is_pro=plans.has_pro(u), pro_until=u.pro_until, pro_source=u.pro_source,
        created_at=u.created_at, favorites_count=favorites,
    )


@router.get("/users", response_model=AdminUsersPage)
async def list_users(
    q: Optional[str] = Query(default=None, max_length=100),
    plan: Literal["all", "pro", "free", "blocked", "admin"] = "all",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Users, newest first, with their favorites count. `q` looks in the
    e-mail and the profile name; `plan` filters: pro (running term), free,
    blocked (deactivated), admin."""
    await plans.expire_due(db)  # expired terms show as Free, with a log row
    where = []
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        where.append(or_(func.lower(User.email).like(like), func.lower(func.coalesce(User.full_name, "")).like(like)))
    if plan == "pro":
        where.append(User.plan == "pro")
    elif plan == "free":
        where.append(User.plan != "pro")
    elif plan == "blocked":
        where.append(User.is_active.is_(False))
    elif plan == "admin":
        where.append(User.is_admin.is_(True))
    total = int(await db.scalar(select(func.count(User.id)).where(*where)) or 0)
    users = (await db.execute(
        select(User).where(*where).order_by(User.created_at.desc(), User.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    favs: dict[int, int] = {}
    if users:
        favs = dict((await db.execute(
            select(Favorite.user_id, func.count(Favorite.id))
            .where(Favorite.user_id.in_([u.id for u in users])).group_by(Favorite.user_id)
        )).all())
    return AdminUsersPage(items=[_admin_user(u, favs.get(u.id, 0)) for u in users],
                          total=total, page=page, page_size=page_size)


@router.patch("/users/{user_id}", response_model=AdminUserRead)
async def patch_user(
    user_id: int,
    patch: AdminUserPatch,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """Block/unblock a user, give Pro for a term or take it away. Every plan
    change goes to the log. Admins cannot deactivate themselves; changing
    their own plan is harmless (admins see Pro features anyway)."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if patch.is_active is not None and user_id == current_admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    changed = False
    if patch.is_active is not None:
        user.is_active = patch.is_active
        db.add(user)
        changed = True
    try:
        if patch.plan == "free":
            plans.revoke(db, user, current_admin, patch.note)
            changed = True
        elif patch.plan == "pro" or patch.pro_days is not None or patch.pro_until is not None or patch.pro_forever:
            plans.grant(db, user, current_admin, days=patch.pro_days, until=patch.pro_until,
                        forever=patch.pro_forever or (patch.pro_days is None and patch.pro_until is None),
                        note=patch.note)
            changed = True
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if changed:
        await db.commit()
        await db.refresh(user)

    fav_count = await db.scalar(
        select(func.count(Favorite.id)).where(Favorite.user_id == user_id)
    ) or 0
    return _admin_user(user, fav_count)


@router.get("/users/{user_id}/plan-log", response_model=List[PlanChangeRead])
async def user_plan_log(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Every Pro grant, extension, revoke and expiry of a user, newest first."""
    rows = await plans.history(db, user_id)
    admin_ids = {r.by_user_id for r in rows if r.by_user_id}
    emails = dict((await db.execute(select(User.id, User.email).where(User.id.in_(admin_ids)))).all()) if admin_ids else {}
    return [
        PlanChangeRead(at=r.at, action=r.action, plan=r.plan, pro_until=r.pro_until, source=r.source,
                       note=r.note, by_email=emails.get(r.by_user_id))
        for r in rows
    ]


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """Hard-delete a user + cascading favorites + preferences. Email is freed.
    Admins cannot delete themselves."""
    if user_id == current_admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    sub = await billing.live_subscription(db, user_id)
    if sub is not None:
        try:
            await billing.cancel_now(sub)  # no more charges for a deleted account
        except billing.PaddleError as e:
            raise HTTPException(status_code=409, detail=f"Could not stop the Paddle subscription: {e}") from e
    await db.execute(delete(Favorite).where(Favorite.user_id == user_id))
    await db.execute(delete(UserPreferences).where(UserPreferences.user_id == user_id))
    await db.execute(delete(PlanChange).where(PlanChange.user_id == user_id))
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()


class BatchDeactivateRequest(BaseModel):
    user_ids: List[int]


@router.post("/users/batch/deactivate")
async def batch_deactivate_users(
    payload: BatchDeactivateRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """Deactivate multiple users at once. Silently skips current admin's own id."""
    safe_ids = [uid for uid in payload.user_ids if uid != current_admin.id]
    skipped_self = len(payload.user_ids) - len(safe_ids)
    if not safe_ids:
        return {"updated": 0, "skipped_self": skipped_self}
    await db.execute(
        update(User).where(User.id.in_(safe_ids)).values(is_active=False)
    )
    await db.commit()
    return {"updated": len(safe_ids), "skipped_self": skipped_self}


@router.get("/logs", response_model=LogsResponse)
async def get_logs(
    tail: int = Query(default=50, ge=1, le=500),
    _: User = Depends(get_current_admin),
):
    """Recent log lines from the in-memory ring buffer."""
    lines = LOG_RING[-tail:] if LOG_RING else ["[No log entries captured yet — start the scraper to populate]"]
    return LogsResponse(lines=lines, total=len(LOG_RING))


# ── Possible duplicates ──────────────────────────────────────────────────────

def _dup_group(gid: Optional[int], name: str, products: list) -> DupGroup:
    """One side of a pair: the cheapest offer per shop and volume."""
    best: dict[tuple[str, str], Product] = {}
    for p in products:
        k = (p.search_term, (p.volume or "").lower())
        cur = best.get(k)
        if cur is None or (p.last_price is not None and (cur.last_price is None or p.last_price < cur.last_price)):
            best[k] = p
    offers = sorted(best.values(), key=lambda p: (group_merge.volume_sort_key(p.volume or ""), p.search_term))
    image = next((p.image_url for p in products if p.image_url and p.is_available), None) \
        or next((p.image_url for p in products if p.image_url), None)
    return DupGroup(
        id=gid, name=name, image_url=image, shops=sorted({p.search_term for p in products}), products=len(products),
        offers=[DupOffer(shop=p.search_term, volume=p.volume, price=float(p.last_price) if p.last_price is not None else None,
                         url=p.url, is_available=p.is_available) for p in offers],
    )


async def _dup_pairs(db: AsyncSession, pairs: list) -> list:
    gids = {g for p in pairs for g in (p.group_a_id, p.group_b_id) if g}
    moved = {i for p in pairs if p.status == "merged" for i in (p.moved_product_ids or [])}
    rows = []
    if gids or moved:
        rows = (await db.execute(select(Product).where(
            or_(Product.group_id.in_(gids or [-1]), Product.id.in_(moved or [-1])),
            Product.card_type == "perfume"))).scalars().all()
    by_group: dict[int, list] = {}
    by_id = {p.id: p for p in rows}
    for p in rows:
        by_group.setdefault(p.group_id, []).append(p)
    out = []
    for pair in pairs:
        if pair.status == "merged":
            ids_b = set(pair.moved_product_ids or [])
            a_products = [p for p in by_group.get(pair.group_a_id, []) if p.id not in ids_b]
            b_products = [by_id[i] for i in ids_b if i in by_id]
        else:
            a_products = by_group.get(pair.group_a_id, [])
            b_products = by_group.get(pair.group_b_id, [])
        a = _dup_group(pair.group_a_id, pair.name_a, a_products)
        b = _dup_group(pair.group_b_id, pair.name_b, b_products)
        common = sorted({(o.volume or "").lower() for o in a.offers} & {(o.volume or "").lower() for o in b.offers} - {""},
                        key=group_merge.volume_sort_key)
        out.append(DupPair(id=pair.id, reason=pair.reason, score=pair.score, status=pair.status,
                           created_at=pair.created_at, decided_at=pair.decided_at, common_volumes=common, a=a, b=b))
    return out


@router.get("/duplicates", response_model=DupPage)
async def list_duplicates(
    status_: Literal["pending", "merged", "different", "undone"] = Query(default="pending", alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Possible duplicates: pending ones by score (most likely first), decided
    ones newest first."""
    total = int(await db.scalar(select(func.count(GroupPair.id)).where(GroupPair.status == status_)) or 0)
    pending = int(await db.scalar(select(func.count(GroupPair.id)).where(GroupPair.status == "pending")) or 0)
    order = (GroupPair.score.desc(), GroupPair.id) if status_ == "pending" else (GroupPair.decided_at.desc(), GroupPair.id.desc())
    pairs = (await db.execute(select(GroupPair).where(GroupPair.status == status_).order_by(*order)
                              .offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return DupPage(items=await _dup_pairs(db, list(pairs)), total=total, pending=pending, page=page, page_size=page_size)


@router.post("/duplicates/scan")
async def scan_duplicates(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_admin)):
    """Look for new possible duplicates now (it also runs after each day scan)."""
    result = await group_merge.find_pairs(db)
    await db.commit()
    return result


@router.post("/duplicates/{pair_id}/{action}")
async def decide_duplicate(
    pair_id: int,
    action: Literal["merge", "keep-apart", "undo"],
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """merge: one card from now on (B's products go to A); keep-apart: never
    propose this pair again; undo: split a merged pair again."""
    pair = await db.get(GroupPair, pair_id)
    if pair is None:
        raise HTTPException(status_code=404, detail="Pair not found")
    try:
        if action == "merge":
            moved = await group_merge.merge_pair(db, pair, admin.id)
        elif action == "undo":
            moved = await group_merge.undo_merge(db, pair, admin.id)
        else:
            await group_merge.keep_apart(db, pair, admin.id)
            moved = 0
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    await db.commit()
    logger.info(f"duplicates: pair {pair_id} {action} by admin {admin.id} ({moved} products)")
    return {"ok": True, "status": pair.status, "moved": moved}
