"""Admin-only API endpoints. All routes require is_admin=True via get_current_admin."""
import time
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.api.deps import get_db, get_current_admin
from app.domain.models import User, ScrapingRule, Product, PriceHistory, Favorite

router = APIRouter(prefix="/admin", tags=["admin"])

# ── In-memory rate limiters ───────────────────────────────────────────────────

_last_scrape: dict[str, float] = {}
_last_regen: dict[str, float] = {}
SCRAPE_COOLDOWN_S = 300   # 5 min between scrapes per domain
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

    rules_result = await db.execute(select(ScrapingRule))
    rules = rules_result.scalars().all()

    sites = []
    for rule in rules:
        pc = await db.scalar(
            select(func.count(Product.id)).where(Product.search_term == rule.domain)
        ) or 0
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


@router.post("/scrape/{domain}")
async def trigger_scrape(
    domain: str,
    _: User = Depends(get_current_admin),
):
    """Trigger an ad-hoc scrape for a domain (rate-limited to once per 5 min)."""
    now = time.time()
    if domain in _last_scrape and now - _last_scrape[domain] < SCRAPE_COOLDOWN_S:
        remaining = int(SCRAPE_COOLDOWN_S - (now - _last_scrape[domain]))
        raise HTTPException(status_code=429, detail=f"Rate limit: retry in {remaining}s")
    _last_scrape[domain] = now
    # Phase 4 TODO: trigger scheduler.trigger_site_scrape(domain)
    return {"status": "queued", "domain": domain}


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


@router.get("/logs", response_model=LogsResponse)
async def get_logs(
    tail: int = Query(default=50, ge=1, le=500),
    _: User = Depends(get_current_admin),
):
    """Recent log lines from the in-memory ring buffer."""
    lines = LOG_RING[-tail:] if LOG_RING else ["[No log entries captured yet — start the scraper to populate]"]
    return LogsResponse(lines=lines, total=len(LOG_RING))
