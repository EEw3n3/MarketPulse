from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc, or_
from sqlalchemy.orm import selectinload
import logging
import uvicorn


class _EndpointFilter(logging.Filter):
    """Suppress uvicorn access log spam for high-frequency polling endpoints."""
    _MUTED = {"/api/admin/logs"}

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(path in msg for path in self._MUTED)


logging.getLogger("uvicorn.access").addFilter(_EndpointFilter())
from app.api.deps import get_db
from app.api import schemas
from app.api.auth import router as auth_router
from app.api.favorites import router as favorites_router
from app.api.analytics import router as analytics_router
from app.api.admin import router as admin_router
from app.api.telegram import router as telegram_router
from app.api.chat import router as chat_router
from app.api.exports import router as exports_router
from app.domain.models import Product, PriceHistory
from app.core.config import settings

app = FastAPI(
    title="MarketPulse API",
    description="Backend API for MarketPulse Price Monitoring System",
    version="1.0.0",
    servers=[
        {"url": "http://46.101.174.12:8000", "description": "Production Server"},
        {"url": "http://localhost:8000", "description": "Local Development"}
    ]
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
app.include_router(auth_router, prefix="/api")
app.include_router(favorites_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(telegram_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(exports_router, prefix="/api")

# --- Startup ---

@app.on_event("startup")
async def wire_log_sink() -> None:
    """Route loguru output into the in-memory ring buffer so /admin/logs works."""
    from loguru import logger
    from app.api.admin import push_log
    logger.add(lambda msg: push_log(msg.strip()), level="INFO", colorize=False)


@app.on_event("startup")
async def register_telegram_webhook() -> None:
    """Telegram setup — polling for dev, webhook for prod."""
    from app.services.telegram_bot import bot
    if not settings.TELEGRAM_BOT_TOKEN:
        return
    if settings.TELEGRAM_POLLING:
        import asyncio
        await bot.delete_webhook()
        asyncio.create_task(bot.start_polling())
    elif settings.PUBLIC_BASE_URL and settings.PUBLIC_BASE_URL.startswith("https://"):
        webhook_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/api/auth/telegram/webhook"
        await bot.set_webhook(webhook_url, secret_token=settings.TELEGRAM_WEBHOOK_SECRET)


@app.on_event("startup")
async def bootstrap_scraping_rules_from_categories() -> None:
    """Ensure a ScrapingRule row exists for every target listed in
    `configs/categories.json`. Without this, newly added retailers don't show
    up in Admin → Scraping until someone successfully scrapes them once —
    chicken-and-egg.

    Now: adding a target to categories.json + restart → row appears in the
    admin panel immediately with `last_scrape_at=NULL` and product_count=0,
    so the operator can click "Scrape now" to bootstrap the new site.

    Idempotent: only inserts rows whose `domain` doesn't already exist.
    """
    import json
    import os
    from urllib.parse import urlparse
    from app.core.database import async_session_maker
    from app.domain.models import ScrapingRule

    cfg_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "configs", "categories.json")
    )
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cats = json.load(f)
    except Exception as exc:
        from loguru import logger
        logger.warning(f"bootstrap_scraping_rules: cannot read categories.json: {exc}")
        return

    discovered: list[tuple[str, str]] = []  # (domain, site_name)
    for category_block in cats.values():
        for target in category_block.get("targets", []):
            url = target.get("url", "")
            site = target.get("site")
            if not url:
                continue
            domain = urlparse(url).netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            if not domain:
                continue
            discovered.append((domain, site or domain))

    if not discovered:
        return

    async with async_session_maker() as session:
        existing_rows = await session.execute(select(ScrapingRule.domain))
        existing = {row[0] for row in existing_rows.all()}

        added = 0
        for domain, site_name in discovered:
            if domain in existing:
                continue
            session.add(ScrapingRule(
                domain=domain,
                site_name=site_name,
                health_score=0.0,
                success_count=0,
                failure_count=0,
            ))
            added += 1

        if added:
            await session.commit()
            from loguru import logger
            logger.info(f"🪴 Bootstrapped {added} new ScrapingRule(s) from categories.json")


# APScheduler disabled — scraping is triggered manually (server-side scraping not yet viable due to IP bans)
# @app.on_event("startup")
# async def start_scheduler() -> None:
#     from app.services.scheduler import scheduler_service
#     scheduler_service.start(interval_hours=settings.SCRAPE_INTERVAL_HOURS)
#
# @app.on_event("shutdown")
# async def stop_scheduler() -> None:
#     from app.services.scheduler import scheduler_service
#     scheduler_service.stop()


# --- Helper Functions ---

_STORE_INITIALS = {
    "notino": "N", "notino.lv": "N",
    "douglas latvia": "D", "douglas.lv": "D",
    "makeup.lv": "M", "makeup": "M",
    "1a.lv": "1",
    "220.lv": "2",
}

_STORE_COLORS = {
    "notino": "bg-[hsl(var(--success))]", "notino.lv": "bg-[hsl(var(--success))]",
    "douglas latvia": "bg-blue-500", "douglas.lv": "bg-blue-500",
    "makeup.lv": "bg-pink-500", "makeup": "bg-pink-500",
    "1a.lv": "bg-orange-500",
    "220.lv": "bg-amber-500",
}

def get_store_initial(store_name: str) -> str:
    return _STORE_INITIALS.get(store_name.lower(), store_name[0].upper() if store_name else "?")

def get_store_color(store_name: str) -> str:
    return _STORE_COLORS.get(store_name.lower(), "bg-gray-500")

def _price_delta(last_price, old_price) -> tuple[int, str]:
    """Returns (rounded_percent, direction) for a price change."""
    if not old_price or float(old_price) == 0:
        return 0, "none"
    diff = float(last_price) - float(old_price)
    if diff > 0.01:
        direction = "up"
    elif diff < -0.01:
        direction = "down"
    else:
        return 0, "none"
    percent = int(round(abs(diff) / float(old_price) * 100))
    return percent, direction

# --- API Endpoints ---

@app.get("/")
async def root():
    return {"message": "Welcome to MarketPulse API", "status": "online"}

@app.get("/api/products/feed", response_model=List[schemas.ProductFeedItem])
async def get_product_feed(
    limit: int = 20,
    brands: List[str] = Query(None),
    stores: List[str] = Query(None),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Latest price changes for the dashboard feed."""
    stmt = select(Product).where(Product.old_price.isnot(None))
    if brands:
        stmt = stmt.where(Product.brand.in_(brands))
    if stores:
        stmt = stmt.where(_store_filter_clause(stores))
    if search:
        stmt = stmt.where(or_(Product.title.ilike(f"%{search}%"), Product.brand.ilike(f"%{search}%")))
    stmt = stmt.order_by(desc(Product.last_seen)).limit(limit)
    result = await db.execute(stmt)
    products = result.scalars().all()
    
    feed_items = []
    for p in products:
        rounded_percent, direction = _price_delta(p.last_price, p.old_price)

        # Skip items with no significant change
        if direction == "none" or rounded_percent == 0:
            continue

        feed_items.append(schemas.ProductFeedItem(
            id=p.id,
            brand=p.brand or "Unknown",
            title=p.title,
            currentPrice=float(p.last_price),
            previousPrice=float(p.old_price) if p.old_price else float(p.last_price),
            changePercent=rounded_percent,
            changeDirection=direction,
            storeInitial=get_store_initial(p.search_term),
            storeName=p.search_term.capitalize(),
            storeColor=get_store_color(p.search_term),
            image_url=p.image_url
        ))
    return feed_items

@app.get("/api/products/brands")
async def get_all_brands(db: AsyncSession = Depends(get_db)) -> List[dict]:
    """All distinct brands with product counts, sorted by count DESC.
    Used by the catalog filter panel to populate the full brand list."""
    stmt = (
        select(Product.brand, func.count(Product.id).label("count"))
        .where(Product.brand.isnot(None), Product.brand != "")
        .group_by(Product.brand)
        .order_by(desc(func.count(Product.id)))
    )
    result = await db.execute(stmt)
    return [{"name": row[0], "count": row[1]} for row in result.all()]


# ── Pretty labels for known stores. Stores not in this map use their raw
# search_term as display label (good enough for newly added stores until UI
# defaults are added).
_STORE_PRETTY_LABELS = {
    "douglas": "Douglas",
    "notino": "Notino",
    "220": "220.lv",
    "makeup": "Makeup.lv",
    "1a": "1a.lv",
}


def _canonical_store_key(search_term: str) -> str:
    """Mirror of frontend's canonicalStore(): lower + strip .lv / latvija / latvia."""
    s = (search_term or "").lower().strip()
    for suffix in (".lv", " latvija", " latvia"):
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip()
            break
    return s


@app.get("/api/products/stores")
async def get_all_stores(db: AsyncSession = Depends(get_db)) -> List[dict]:
    """All stores currently present in the catalog, with product counts.

    Used by the catalog filter panel — combined with the hardcoded
    STORE_OPTIONS on the frontend, this lets newly added retailers
    (added via configs/categories.json + first scrape) appear in the
    filter automatically without a frontend rebuild.

    Stores with `count == 0` are also returned so the frontend can mark
    them as "in progress" (existing pattern, e.g. 1a.lv when Cloudflare
    blocks scraping).
    """
    stmt = (
        select(Product.search_term, func.count(Product.id).label("count"))
        .where(Product.search_term.isnot(None), Product.search_term != "")
        .group_by(Product.search_term)
    )
    result = await db.execute(stmt)
    rows = result.all()

    # Aggregate by canonical key (collapses "Notino" + "notino.lv" into one).
    aggregated: dict[str, int] = {}
    for search_term, count in rows:
        key = _canonical_store_key(search_term)
        if not key:
            continue
        aggregated[key] = aggregated.get(key, 0) + int(count or 0)

    payload = [
        {
            "key": key,
            "label": _STORE_PRETTY_LABELS.get(key, key),
            "count": count,
        }
        for key, count in sorted(aggregated.items(), key=lambda kv: kv[1], reverse=True)
    ]
    return payload


def _store_filter_clause(stores: List[str]):
    """Case-insensitive substring match for stores. Frontend sends canonical keys
    ("notino", "douglas", "220", "makeup", "1a") — DB has mixed forms like
    "Notino", "notino.lv", "Douglas Latvia", "Makeup latvija", "1A.LV". A LOWER()
    LIKE %key% matches all variants reliably."""
    return or_(*(func.lower(Product.search_term).like(f"%{s.lower()}%") for s in stores))


def _catalog_base_stmt(search: Optional[str], brands: Optional[List[str]], stores: Optional[List[str]]):
    """Shared filter logic for catalog endpoints."""
    stmt = select(Product)
    if search:
        stmt = stmt.where(or_(Product.title.ilike(f"%{search}%"), Product.brand.ilike(f"%{search}%")))
    if brands:
        stmt = stmt.where(Product.brand.in_(brands))
    if stores:
        stmt = stmt.where(_store_filter_clause(stores))
    return stmt


@app.get("/api/products/catalog/count")
async def get_catalog_count(
    search: Optional[str] = None,
    brands: List[str] = Query(None),
    stores: List[str] = Query(None),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Total number of products matching the given filters."""
    stmt = select(func.count()).select_from(_catalog_base_stmt(search, brands, stores).subquery())
    total = await db.scalar(stmt)
    return {"total": int(total or 0)}


@app.get("/api/products/catalog", response_model=List[schemas.CatalogItem])
async def get_catalog(
    search: Optional[str] = None,
    brands: List[str] = Query(None),
    stores: List[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Full catalog with filtering and search."""
    stmt = _catalog_base_stmt(search, brands, stores).offset(skip).limit(limit)
    result = await db.execute(stmt)
    products = result.scalars().all()
    
    catalog_items = []
    for p in products:
        rounded_percent, direction = _price_delta(p.last_price, p.old_price)

        catalog_items.append(schemas.CatalogItem(
            id=p.id,
            sku=f"MP-{p.id}",
            brand=p.brand or "Unknown",
            name=p.title,
            volume=p.volume or "N/A",
            type=p.concentration or "EDT",
            price=float(p.last_price),
            previousPrice=float(p.old_price) if p.old_price else float(p.last_price),
            changePercent=rounded_percent,
            changeDirection=direction,
            store=p.search_term.capitalize(),
            storeColor=get_store_color(p.search_term),
            in_stock=p.is_available,
            lastUpdated=p.last_seen.strftime("%Y-%m-%d")
        ))
    return catalog_items

def _norm_volume(v: Optional[str]) -> str:
    return (v or "").lower().replace(" ", "").strip()


def _norm_store(s: Optional[str]) -> str:
    return (s or "").lower().replace(".lv", "").replace(" latvia", "").strip()


@app.get("/api/products/{product_id}", response_model=schemas.ProductCardDetail)
async def get_product_detail(product_id: int, db: AsyncSession = Depends(get_db)):
    """Detail view for a single product with history and per-store offers.

    Offers are deduplicated: one row per unique store (cheapest), filtered to the
    same `volume` as the requested product. If a store carries multiple listings
    at the same volume, the extras are surfaced via `variants` for popover."""
    from collections import defaultdict

    stmt = (
        select(Product)
        .options(selectinload(Product.history))
        .where(Product.id == product_id)
    )
    result = await db.execute(stmt)
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Pull all in-stock, priced products in the group (incl. self).
    group_products: list[Product] = []
    if product.group_id:
        grp_stmt = select(Product).where(
            Product.group_id == product.group_id,
            Product.is_available == True,           # noqa: E712
            Product.last_price.isnot(None),
            Product.last_price > 0,
        )
        grp_res = await db.execute(grp_stmt)
        group_products = list(grp_res.scalars().all())

    target_volume = _norm_volume(product.volume)
    # If current product has no volume (gift sets), don't filter by volume.
    volume_filtered = [
        p for p in group_products
        if not target_volume or _norm_volume(p.volume) == target_volume
    ]

    # Group by normalized store name; cheapest = main, rest = variants.
    by_store: dict[str, list[Product]] = defaultdict(list)
    for p in volume_filtered:
        by_store[_norm_store(p.search_term)].append(p)

    offers: list[schemas.StoreOffer] = []
    for _, items in by_store.items():
        items.sort(key=lambda p: float(p.last_price))
        main = items[0]
        extras = items[1:]
        cp_percent, cp_direction = _price_delta(main.last_price, main.old_price)
        offers.append(schemas.StoreOffer(
            product_id=main.id,
            url=main.url,
            storeName=main.search_term.capitalize(),
            storeInitial=get_store_initial(main.search_term),
            storeColor=get_store_color(main.search_term),
            price=float(main.last_price),
            previousPrice=float(main.old_price) if main.old_price else float(main.last_price),
            changePercent=cp_percent,
            changeDirection=cp_direction,
            image_url=main.image_url,
            concentration=main.concentration,
            variants=[
                schemas.StoreOfferVariant(
                    product_id=e.id,
                    price=float(e.last_price),
                    url=e.url,
                    image_url=e.image_url,
                    concentration=e.concentration,
                )
                for e in extras
            ],
        ))

    # Sort stores by their cheapest price ASC, cap at 5 unique stores
    offers.sort(key=lambda o: o.price)
    offers = offers[:5]

    # Use the product's own image — keeps the catalog card and detail page in
    # sync. Earlier we substituted a competitor image for 220.lv listings, but
    # that pulled in mismatched products (different concentration / form factor)
    # whenever cross-site grouping was imperfect. Better to show the real image.
    display_image = product.image_url

    # History: gather PriceHistory for products in the same group that share
    # the SAME volume as the requested product (matches the offer-list filter).
    # Without this filter we leaked history from other volumes — e.g. opening
    # "JPG Le Male 40ml" (only on Makeup) showed a Notino line because the
    # group also contained 75 ml on Notino. The chart's "N stores" count would
    # then disagree with the "1 store" price comparison sidebar — confusing.
    history_items: list[schemas.PriceHistoryRead] = []
    if product.group_id:
        same_volume_ids = [p.id for p in volume_filtered]
        if same_volume_ids:
            grp_hist_stmt = (
                select(PriceHistory, Product.search_term)
                .join(Product, Product.id == PriceHistory.product_id)
                .where(PriceHistory.product_id.in_(same_volume_ids))
                .order_by(PriceHistory.parsed_at.asc())
            )
            rows = (await db.execute(grp_hist_stmt)).all()
            history_items = [
                schemas.PriceHistoryRead(
                    id=h.id,
                    price=h.price,
                    in_stock=h.in_stock,
                    parsed_at=h.parsed_at,
                    change_type=h.change_type,
                    store_name=(search_term or "").lower(),
                )
                for h, search_term in rows
            ]
    if not history_items:
        history_items = [
            schemas.PriceHistoryRead(
                id=h.id, price=h.price, in_stock=h.in_stock,
                parsed_at=h.parsed_at, change_type=h.change_type,
                store_name=(product.search_term or "").lower(),
            )
            for h in product.history
        ]

    return schemas.ProductCardDetail(
        id=product.id,
        url=product.url,
        title=product.title,
        brand=product.brand,
        volume=product.volume,
        concentration=product.concentration,
        image_url=display_image,
        description=product.description,
        current_price=float(product.last_price),
        old_price=float(product.old_price) if product.old_price else None,
        store_name=product.search_term.capitalize(),
        is_available=product.is_available,
        history=history_items,
        offers=offers,
    )

@app.get("/api/analytics/stats", response_model=schemas.DashboardStats)
async def get_analytics_stats(db: AsyncSession = Depends(get_db)):
    """KPIs for the analytics page."""
    total_products = await db.scalar(select(func.count(Product.id)))
    stores_count = await db.scalar(select(func.count(func.distinct(Product.search_term))))

    # Average % price change across products that have an old price
    avg_raw = await db.scalar(
        select(func.avg(
            (Product.last_price - Product.old_price) / Product.old_price * 100
        )).where(
            Product.old_price.isnot(None),
            Product.old_price > 0,
            Product.last_price.isnot(None),
            Product.last_price > 0,
        )
    )
    avg_change = float(avg_raw) if avg_raw is not None else 0.0
    avg_change_str = f"{avg_change:+.1f}%"

    # Potential savings: for each ProductGroup with multiple offers, sum (max - min) price
    savings_subq = (
        select(func.max(Product.last_price) - func.min(Product.last_price))
        .where(Product.group_id.isnot(None), Product.last_price.isnot(None), Product.last_price > 0)
        .group_by(Product.group_id)
        .having(func.count(Product.id) > 1)
        .subquery()
    )
    savings_raw = await db.scalar(select(func.sum(savings_subq.c[0])))
    savings = float(savings_raw) if savings_raw else 0.0
    savings_str = f"€{savings:.0f}"

    # Alerts: price drops and restocks in the last 7 days
    week_ago = datetime.utcnow() - timedelta(days=7)
    alerts_count = await db.scalar(
        select(func.count(PriceHistory.id)).where(
            PriceHistory.change_type.in_(["price_down", "back_in_stock"]),
            PriceHistory.parsed_at >= week_ago,
        )
    )

    return schemas.DashboardStats(
        total_products=f"{total_products:,}",
        avg_price_change=avg_change_str,
        stores_monitored=stores_count or 0,
        potential_savings=savings_str,
        alerts_triggered=int(alerts_count or 0),
    )

if __name__ == "__main__":
    uvicorn.run("app.api.main:app", host="0.0.0.0", port=8000, reload=True)
