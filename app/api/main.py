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
from app.api.deps import get_db, get_current_user, get_pro_user
from app.api import schemas
from app.api.auth import router as auth_router
from app.api.favorites import router as favorites_router
from app.api.analytics import router as analytics_router
from app.api.admin import router as admin_router
from app.api.telegram import router as telegram_router
from app.api.chat import router as chat_router
from app.api.exports import router as exports_router
from app.api.cards import router as cards_router
from app.api.public import router as public_router
from app.api.catalog_filters import (
    _brand_filter_clause,
    _expand_search_term_with_aliases,
    apply_product_filters,
    _store_filter_clause,
)
from app.domain.models import Product, PriceHistory
from app.core.config import settings
from app.services.price_series import (
    by_store as series_by_store,
    cheapest_shop_by_day,
    day_range,
    display_name,
    product_series,
)
from collections import defaultdict

app = FastAPI(
    title="MarketPulse API",
    description="Backend API for MarketPulse Price Monitoring System",
    version="1.0.0",
    servers=[
        {"url": "https://marketpulse1.me", "description": "Production Server"},
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
    # Lets the browser read the export file name when the UI runs on another port.
    expose_headers=["Content-Disposition"],
)

# --- Routers ---
# Catalog, analytics and export data are for signed-in users only;
# /api/auth/register and /api/auth/login stay public.
_LOGIN_REQUIRED = [Depends(get_current_user)]
_PRO_REQUIRED = [Depends(get_pro_user)]

app.include_router(auth_router, prefix="/api")
app.include_router(favorites_router, prefix="/api")
# The analytics cabinet and data exports are Pro features (admins included).
app.include_router(analytics_router, prefix="/api", dependencies=_PRO_REQUIRED)
app.include_router(admin_router, prefix="/api")
app.include_router(telegram_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(exports_router, prefix="/api", dependencies=_PRO_REQUIRED)
# Before the /api/products/{product_id} route below, so /cards etc. win.
app.include_router(cards_router, prefix="/api")
app.include_router(public_router, prefix="/api")

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
    chicken-and-egg. With it, adding a target to categories.json + restart
    makes the row appear with `last_success=NULL` and product_count=0, so the
    operator can click "Scrape now" to bootstrap the new site.

    Idempotent: only inserts rows whose `domain` doesn't already exist.

    Wrapped in a single try/except — even if a bug here would otherwise crash
    startup (and 502 the whole API), we'd rather log the failure and continue
    serving than break login for a non-critical bootstrap step.
    """
    from loguru import logger
    try:
        import json
        import os
        from urllib.parse import urlparse
        from app.core.database import async_session_maker
        from app.domain.models import ScrapingRule

        cfg_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "configs", "categories.json")
        )
        with open(cfg_path, "r", encoding="utf-8") as f:
            cats = json.load(f)

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
                # `container_css` / `title_css` are NOT NULL in the model — we
                # leave them empty here, the first scrape's AI self-healing
                # path populates them with real selectors before any data
                # extraction is attempted.
                session.add(ScrapingRule(
                    domain=domain,
                    site_name=site_name,
                    container_css="",
                    title_css="",
                    success_count=0,
                    failure_count=0,
                ))
                added += 1

            if added:
                await session.commit()
                logger.info(f"🪴 Bootstrapped {added} new ScrapingRule(s) from categories.json")
    except Exception as exc:
        logger.warning(f"bootstrap_scraping_rules failed (non-fatal): {exc!r}")


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

@app.get("/api/products/feed", response_model=List[schemas.ProductFeedItem], dependencies=_LOGIN_REQUIRED)
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
        stmt = stmt.where(_brand_filter_clause(brands))
    if stores:
        stmt = stmt.where(_store_filter_clause(stores))
    if search:
        # Brand-alias expansion: JPG → Jean Paul Gaultier, YSL → Yves Saint Laurent, etc.
        search_variants = _expand_search_term_with_aliases(search)
        ors = []
        for s in search_variants:
            ors.append(Product.title.ilike(f"%{s}%"))
            ors.append(Product.brand.ilike(f"%{s}%"))
        stmt = stmt.where(or_(*ors))
    # Over-fetch: the same physical product can exist as several DB rows
    # (Notino serves one item under multiple URL forms, e.g. ".../slug/" and
    # ".../slug/p-12345/", which created duplicate Product records with desynced
    # prices). We de-duplicate below and apply `limit` only AFTER that, so we
    # must pull more candidates than requested. Capped to avoid scanning the
    # whole table.
    fetch_cap = max(limit * 6, 300)
    stmt = stmt.order_by(desc(Product.last_seen)).limit(fetch_cap)
    result = await db.execute(stmt)
    products = result.scalars().all()

    feed_items = []
    seen_keys: set = set()
    for p in products:
        rounded_percent, direction = _price_delta(p.last_price, p.old_price)

        # Skip items with no significant change
        if direction == "none" or rounded_percent == 0:
            continue

        # De-duplicate: collapse multiple rows of the SAME perfume (brand +
        # title + volume + concentration + store) into one. Rows are ordered
        # last_seen DESC, so the first one seen is the freshest — keep it, drop
        # the rest. Different concentrations (EDT vs EDP vs Parfum) have distinct
        # keys, so they correctly remain separate cards.
        dedupe_key = (
            (p.brand or "").lower(),
            (p.title or "").lower(),
            (p.volume or "").lower(),
            (p.concentration or "").lower(),
            (p.search_term or "").lower(),
        )
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        # Surface concentration in the card title so genuinely different
        # variants (EDT/EDP/Parfum) of the same name+volume are visually
        # distinguishable instead of looking like duplicates.
        display_title = p.title or ""
        conc = (p.concentration or "").strip()
        if conc and conc.lower() not in display_title.lower():
            display_title = f"{display_title} · {conc}"

        feed_items.append(schemas.ProductFeedItem(
            id=p.id,
            brand=p.brand or "Unknown",
            title=display_title,
            currentPrice=float(p.last_price),
            previousPrice=float(p.old_price) if p.old_price else float(p.last_price),
            changePercent=rounded_percent,
            changeDirection=direction,
            storeInitial=get_store_initial(p.search_term),
            storeName=p.search_term.capitalize(),
            storeColor=get_store_color(p.search_term),
            image_url=p.image_url,
            lastUpdated=p.last_seen.isoformat() if p.last_seen else "",
        ))
        if len(feed_items) >= limit:
            break
    return feed_items

@app.get("/api/products/brands", dependencies=_LOGIN_REQUIRED)
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


@app.get("/api/products/volumes", dependencies=_LOGIN_REQUIRED)
async def get_all_volumes(db: AsyncSession = Depends(get_db)) -> List[dict]:
    """All distinct volumes with product counts, sorted by canonical ml ASC.

    Used by the catalog filter panel. Volumes come from `Product.volume` as
    strings like "50ml", "100ml" — we extract the numeric component for
    sorting so 100ml > 75ml > 50ml, not lexicographic "100ml" < "50ml".
    """
    import re
    stmt = (
        select(Product.volume, func.count(Product.id).label("count"))
        .where(Product.volume.isnot(None), Product.volume != "")
        .group_by(Product.volume)
    )
    result = await db.execute(stmt)
    rows = result.all()

    def _ml(v: str) -> int:
        m = re.search(r"(\d+)", v or "")
        return int(m.group(1)) if m else 0

    payload = [{"value": row[0], "count": int(row[1] or 0)} for row in rows]
    payload.sort(key=lambda r: _ml(r["value"]))
    return payload


@app.get("/api/products/stores", dependencies=_LOGIN_REQUIRED)
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


def _catalog_base_stmt(
    search: Optional[str],
    brands: Optional[List[str]],
    stores: Optional[List[str]],
    volumes: Optional[List[str]] = None,
    types: Optional[List[str]] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    in_stock: Optional[bool] = None,
):
    """Shared filter logic for catalog endpoints."""
    # A product that never had a price (last_price 0) would show as "0 €".
    stmt = select(Product).where(Product.last_price > 0)
    return apply_product_filters(
        stmt, search=search, brands=brands, stores=stores, volumes=volumes,
        types=types, price_min=price_min, price_max=price_max, in_stock=in_stock,
    )


@app.get("/api/products/catalog/count", dependencies=_LOGIN_REQUIRED)
async def get_catalog_count(
    search: Optional[str] = None,
    brands: List[str] = Query(None),
    stores: List[str] = Query(None),
    volumes: List[str] = Query(None),
    types: List[str] = Query(None),
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    in_stock: Optional[bool] = None,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Total number of products matching the given filters."""
    stmt = select(func.count()).select_from(_catalog_base_stmt(search, brands, stores, volumes, types, price_min, price_max, in_stock).subquery())
    total = await db.scalar(stmt)
    return {"total": int(total or 0)}


@app.get("/api/products/catalog", response_model=List[schemas.CatalogItem], dependencies=_LOGIN_REQUIRED)
async def get_catalog(
    search: Optional[str] = None,
    brands: List[str] = Query(None),
    stores: List[str] = Query(None),
    volumes: List[str] = Query(None),
    types: List[str] = Query(None),
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    in_stock: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Full catalog with filtering and search."""
    stmt = _catalog_base_stmt(search, brands, stores, volumes, types, price_min, price_max, in_stock).offset(skip).limit(limit)
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
            lastUpdated=p.last_seen.strftime("%Y-%m-%d"),
            promoPrice=float(p.promo_price) if p.promo_price else None,
            promoCode=p.promo_code,
        ))
    return catalog_items

def _ml(v: Optional[str]) -> float:
    import re
    m = re.search(r"(\d+(?:[.,]\d+)?)", v or "")
    return float(m.group(1).replace(",", ".")) if m else 0.0


def _norm_volume(v: Optional[str]) -> str:
    return (v or "").lower().replace(" ", "").strip()


def _norm_store(s: Optional[str]) -> str:
    return (s or "").lower().replace(".lv", "").replace(" latvia", "").strip()


@app.get("/api/products/{product_id}", response_model=schemas.ProductCardDetail, dependencies=_LOGIN_REQUIRED)
async def get_product_detail(product_id: int, db: AsyncSession = Depends(get_db)):
    """Detail view for a single product with history and per-store offers.

    Offers are deduplicated: one row per unique store (cheapest), filtered to the
    same `volume` as the requested product. If a store carries multiple listings
    at the same volume, the extras are surfaced via `variants` for popover."""
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
            promoPrice=float(main.promo_price) if main.promo_price else None,
            promoCode=main.promo_code,
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

    # Redesign extras: other sizes of the same perfume and a daily series per
    # shop. The series uses every listing of this size, in stock or not, so a
    # shop's line stops where it ran out instead of vanishing.
    sizes: list[schemas.SizeOption] = []
    by_volume: dict[str, list[Product]] = defaultdict(list)
    for p in group_products:
        if p.volume:
            by_volume[_norm_volume(p.volume)].append(p)
    for items in by_volume.values():
        items.sort(key=lambda p: float(p.last_price))
        sizes.append(schemas.SizeOption(
            product_id=items[0].id,
            volume=items[0].volume,
            min_price=float(items[0].last_price),
            shops=len({_norm_store(p.search_term) for p in items}),
        ))
    sizes.sort(key=lambda o: _ml(o.volume))

    if product.group_id:
        same_size = (await db.execute(select(Product).where(
            Product.group_id == product.group_id,
            Product.last_price > 0,
        ))).scalars().all()
        same_size = [p for p in same_size if not target_volume or _norm_volume(p.volume) == target_volume]
    else:
        same_size = [product]
    if product not in same_size:
        same_size.append(product)
    first_day = min((h.parsed_at for h in history_items), default=None)
    span = (datetime.utcnow().date() - first_day.date()).days + 1 if first_day else 30
    days = day_range(max(30, min(span, 365)))
    per_product = await product_series(db, same_size, days)
    shop_lines = series_by_store(same_size, per_product)
    series = schemas.PriceSeries(
        days=[d.isoformat() for d in days],
        shops=shop_lines,
        cheapest=cheapest_shop_by_day(shop_lines),
    )

    return schemas.ProductCardDetail(
        display_name=display_name(same_size),
        sizes=sizes,
        series=series,
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
        promo_price=float(product.promo_price) if product.promo_price else None,
        promo_code=product.promo_code,
        history=history_items,
        offers=offers,
    )

@app.get("/api/analytics/stats", response_model=schemas.DashboardStats, dependencies=_LOGIN_REQUIRED)
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
