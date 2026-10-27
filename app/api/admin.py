"""Admin-only API endpoints. All routes require is_admin=True via get_current_admin."""
import re
import time
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, delete, update, or_

from app.api.deps import get_db, get_current_admin, get_worker
from app.core.job_queue import job_queue
from app.domain.models import User, ScrapingRule, Product, PriceHistory, Favorite, UserPreferences

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

class DataQualityResponse(BaseModel):
    total_products: int
    products_without_image: int
    products_without_history: int
    products_ungrouped: int
    total_price_events: int

class AdminUserRead(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    is_active: bool
    is_admin: bool
    created_at: datetime
    favorites_count: int = 0

class AdminUserPatch(BaseModel):
    is_active: Optional[bool] = None

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

    inserted = 0
    updated = 0
    price_changes = 0

    for item in payload.products:
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
                group_id = resolved.id

            product = Product(
                url=item.url,
                title=item.title,
                brand=item.brand,
                volume=item.volume,
                concentration=item.concentration,
                image_url=item.image_url,
                search_term=payload.domain,
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
            product.brand = item.brand or product.brand
            product.volume = item.volume or product.volume
            product.concentration = item.concentration or product.concentration
            if item.image_url:
                product.image_url = item.image_url
            product.is_available = item.is_available
            product.last_seen = datetime.utcnow()
            product.card_type = item.card_type
            if item.card_type != "perfume":
                product.group_id = None
            product.promo_price = promo_dec
            product.promo_code = item.promo_code

            if price_dec is not None and price_dec > 0:
                old = product.last_price
                if old != price_dec:
                    if old is not None and price_dec < old:
                        change = "price_down"
                    elif old is not None and price_dec > old:
                        change = "price_up"
                    else:
                        change = "initial"
                    product.old_price = old
                    product.last_price = price_dec
                    db.add(PriceHistory(
                        product_id=product.id, price=price_dec,
                        in_stock=item.is_available, change_type=change,
                    ))
                    price_changes += 1

    await db.commit()
    return {"inserted": inserted, "updated": updated, "price_changes": price_changes}


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

    state = await job_queue.get_state(job_id)
    domain = (state or {}).get("domain")
    if domain:
        rule = await db.scalar(select(ScrapingRule).where(ScrapingRule.domain == domain))
        if rule:
            if status == "done":
                rule.last_success = datetime.utcnow()
                rule.success_count += 1
                rule.last_error = None
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
    )


@router.get("/users", response_model=List[AdminUserRead])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """All registered users with favorites count."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()

    out: list[AdminUserRead] = []
    for u in users:
        fav_count = await db.scalar(
            select(func.count(Favorite.id)).where(Favorite.user_id == u.id)
        ) or 0
        out.append(AdminUserRead(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            is_active=u.is_active,
            is_admin=u.is_admin,
            created_at=u.created_at,
            favorites_count=fav_count,
        ))
    return out


@router.patch("/users/{user_id}", response_model=AdminUserRead)
async def patch_user(
    user_id: int,
    patch: AdminUserPatch,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """Toggle is_active on a user. Admins cannot deactivate themselves."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user_id == current_admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    if patch.is_active is not None:
        user.is_active = patch.is_active
        db.add(user)
        await db.commit()
        await db.refresh(user)

    fav_count = await db.scalar(
        select(func.count(Favorite.id)).where(Favorite.user_id == user_id)
    ) or 0

    return AdminUserRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
        favorites_count=fav_count,
    )


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
    await db.execute(delete(Favorite).where(Favorite.user_id == user_id))
    await db.execute(delete(UserPreferences).where(UserPreferences.user_id == user_id))
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
