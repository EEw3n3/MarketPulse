"""Analytics endpoints — aggregate views for the B2B analytical cabinet.

All endpoints need the Pro plan (see app/api/main.py); admins always pass.

Five views, each computed live from Postgres on every request. With ~400 products
this is fine; if catalog grows past ~10k products we should add a materialized
view layer.
"""
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api import schemas
from app.api.deps import get_db
from app.domain.models import PriceHistory, Product, ProductGroup

router = APIRouter(prefix="/analytics", tags=["analytics"])


_WINDOW_DAYS = {"24h": 1, "7d": 7, "30d": 30, "90d": 90}


# ─────────────────────────────────────────────────────────────────────────────
# 1. Top movers
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/movers", response_model=list[schemas.MoverItem])
async def movers(
    window: Literal["24h", "7d", "30d"] = "7d",
    limit: int = Query(20, ge=1, le=100),
    direction: Literal["both", "up", "down"] = "both",
    db: AsyncSession = Depends(get_db),
):
    """Biggest price movements across the whole catalog within the window.

    Strategy: per-product, find the earliest PriceHistory row inside the window
    and compare to current Product.last_price. Falls back to Product.old_price
    if no history row exists in the window (covers products scraped < window
    start where old_price already encodes the previous observation).
    """
    days = _WINDOW_DAYS[window]
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Earliest history row per product within window (Postgres window function)
    ranked = (
        select(
            PriceHistory.product_id.label("pid"),
            PriceHistory.price.label("start_price"),
            func.row_number()
            .over(
                partition_by=PriceHistory.product_id,
                order_by=PriceHistory.parsed_at.asc(),
            )
            .label("rn"),
        )
        .where(PriceHistory.parsed_at >= cutoff)
        .subquery()
    )

    earliest = (
        select(ranked.c.pid, ranked.c.start_price)
        .where(ranked.c.rn == 1)
        .subquery()
    )

    stmt = (
        select(Product, earliest.c.start_price)
        .outerjoin(earliest, earliest.c.pid == Product.id)
        .where(Product.last_price.isnot(None))
    )
    rows = (await db.execute(stmt)).all()

    items: list[schemas.MoverItem] = []
    for product, start_price_history in rows:
        # Prefer history-based start; fall back to old_price for products not yet
        # observed inside the window but with a denormalized previous price.
        start_price = start_price_history if start_price_history is not None else product.old_price
        if start_price is None or float(start_price) == 0:
            continue
        current = float(product.last_price)
        start = float(start_price)
        delta = current - start
        if abs(delta) < 0.01:
            continue
        change_pct = delta / start * 100
        if abs(change_pct) < 0.5:
            continue  # filter rounding noise

        dir_: Literal["up", "down"] = "up" if delta > 0 else "down"
        if direction != "both" and direction != dir_:
            continue

        items.append(
            schemas.MoverItem(
                product_id=product.id,
                brand=product.brand,
                title=product.title,
                image_url=product.image_url,
                store_name=(product.search_term or "unknown").capitalize(),
                current_price=round(current, 2),
                start_price=round(start, 2),
                change_abs=round(delta, 2),
                change_percent=round(change_pct, 2),
                direction=dir_,
            )
        )

    items.sort(key=lambda m: abs(m.change_percent), reverse=True)
    return items[:limit]


# ─────────────────────────────────────────────────────────────────────────────
# 2. Biggest spreads (cross-store arbitrage opportunities)
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/spreads", response_model=list[schemas.SpreadItem])
async def spreads(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """For every ProductGroup with offers in 2+ DISTINCT retailers, return the
    gap between cheapest and most expensive offer. Sorted by spread_percent
    descending. Intra-store groups (same retailer, different sizes) are
    filtered out — those are size variations, not arbitrage.
    """
    # Aggregate per group: min, max, distinct-store count
    group_stats = (
        select(
            Product.group_id.label("gid"),
            func.min(Product.last_price).label("min_p"),
            func.max(Product.last_price).label("max_p"),
            func.count(Product.id).label("cnt"),
            func.count(func.distinct(Product.search_term)).label("store_n"),
        )
        .where(
            Product.group_id.isnot(None),
            Product.last_price.isnot(None),
            Product.last_price > 0,
        )
        .group_by(Product.group_id)
        .having(func.count(func.distinct(Product.search_term)) > 1)
        .subquery()
    )

    # Join group name + image candidate (one product per group is fine for image)
    stmt = (
        select(
            group_stats.c.gid,
            group_stats.c.min_p,
            group_stats.c.max_p,
            group_stats.c.store_n,
            ProductGroup.name,
        )
        .join(ProductGroup, ProductGroup.id == group_stats.c.gid)
    )
    summary_rows = (await db.execute(stmt)).all()

    if not summary_rows:
        return []

    # Pre-rank by spread_percent so we only resolve product details for the top N
    ranked: list[tuple[int, float, float, int, str, float, float]] = []
    for gid, min_p, max_p, store_n, name in summary_rows:
        min_v, max_v = float(min_p), float(max_p)
        if min_v <= 0:
            continue
        spread_abs = max_v - min_v
        if spread_abs < 0.01:
            continue
        spread_pct = spread_abs / min_v * 100
        ranked.append((gid, min_v, max_v, int(store_n), name, spread_abs, spread_pct))

    ranked.sort(key=lambda r: r[6], reverse=True)
    top = ranked[:limit]
    if not top:
        return []

    # Resolve cheapest + most expensive product for each top group in one query
    top_gids = [r[0] for r in top]
    products_in_top = (
        await db.execute(
            select(Product).where(Product.group_id.in_(top_gids), Product.last_price.isnot(None))
        )
    ).scalars().all()

    by_group: dict[int, list[Product]] = {}
    for p in products_in_top:
        by_group.setdefault(p.group_id, []).append(p)

    items: list[schemas.SpreadItem] = []
    for gid, min_v, max_v, store_n, name, spread_abs, spread_pct in top:
        bucket = by_group.get(gid) or []
        if not bucket:
            continue
        cheapest = min(bucket, key=lambda p: float(p.last_price))
        most_exp = max(bucket, key=lambda p: float(p.last_price))
        # Skip degenerate cases where cheapest and most-expensive are the same store
        # (intra-store size variation slipping through despite the distinct-store filter).
        if cheapest.search_term == most_exp.search_term:
            continue
        image_url = cheapest.image_url
        if not image_url:
            for p in bucket:
                if p.image_url:
                    image_url = p.image_url
                    break

        items.append(
            schemas.SpreadItem(
                group_id=gid,
                name=name,
                image_url=image_url,
                cheapest_product_id=cheapest.id,
                cheapest_store=(cheapest.search_term or "unknown").capitalize(),
                cheapest_price=round(float(cheapest.last_price), 2),
                most_expensive_store=(most_exp.search_term or "unknown").capitalize(),
                most_expensive_price=round(float(most_exp.last_price), 2),
                spread_abs=round(spread_abs, 2),
                spread_percent=round(spread_pct, 2),
                store_count=store_n,
            )
        )

    return items


# ─────────────────────────────────────────────────────────────────────────────
# 3. Per-retailer profile
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/retailers", response_model=list[schemas.RetailerStats])
async def retailers(db: AsyncSession = Depends(get_db)):
    """One row per retailer (Product.search_term). Stats:
       - product_count, avg_price
       - drop_count / drop_rate: products with last_price < old_price
       - cheapest_wins / cheapest_win_rate: how often this store has the lowest
         price within a multi-store ProductGroup
    """
    stmt = (
        select(
            Product.search_term.label("store"),
            func.count(Product.id).label("cnt"),
            func.avg(Product.last_price).label("avg_p"),
            func.sum(
                case(
                    (
                        and_(
                            Product.old_price.isnot(None),
                            Product.last_price < Product.old_price,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("drops"),
        )
        .where(Product.last_price.isnot(None), Product.search_term.isnot(None))
        .group_by(Product.search_term)
    )
    rows = (await db.execute(stmt)).all()

    # "Cheapest wins" needs cross-product comparison within group → separate query.
    # Restrict to TRUE cross-store groups (≥2 distinct retailers) so intra-store
    # size variations don't inflate win-rates.
    cheapest_subq = (
        select(
            Product.group_id.label("gid"),
            func.min(Product.last_price).label("min_p"),
        )
        .where(Product.group_id.isnot(None), Product.last_price.isnot(None))
        .group_by(Product.group_id)
        .having(func.count(func.distinct(Product.search_term)) > 1)
        .subquery()
    )

    win_stmt = (
        select(
            Product.search_term.label("store"),
            func.count(Product.id).label("wins"),
        )
        .join(
            cheapest_subq,
            and_(
                cheapest_subq.c.gid == Product.group_id,
                cheapest_subq.c.min_p == Product.last_price,
            ),
        )
        .group_by(Product.search_term)
    )
    wins_by_store = {
        store: wins for store, wins in (await db.execute(win_stmt)).all()
    }

    # Total multi-store groups (denominator for cheapest_win_rate)
    presence_stmt = (
        select(
            Product.search_term.label("store"),
            func.count(func.distinct(Product.group_id)).label("group_presence"),
        )
        .join(cheapest_subq, cheapest_subq.c.gid == Product.group_id)
        .group_by(Product.search_term)
    )
    presence_by_store = {
        store: presence for store, presence in (await db.execute(presence_stmt)).all()
    }

    out: list[schemas.RetailerStats] = []
    for store, cnt, avg_p, drops in rows:
        wins = int(wins_by_store.get(store, 0))
        presence = int(presence_by_store.get(store, 0))
        out.append(
            schemas.RetailerStats(
                store=(store or "unknown").capitalize(),
                product_count=int(cnt),
                avg_price=round(float(avg_p) if avg_p else 0.0, 2),
                drop_count=int(drops or 0),
                drop_rate=round((int(drops or 0) / cnt * 100) if cnt else 0.0, 1),
                cheapest_wins=wins,
                cheapest_win_rate=round((wins / presence * 100) if presence else 0.0, 1),
            )
        )

    out.sort(key=lambda r: r.product_count, reverse=True)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 4. Brand × Store heatmap
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/brand-store-matrix", response_model=list[schemas.BrandStoreCell])
async def brand_store_matrix(
    min_count: int = Query(1, ge=1, description="Skip cells with fewer products"),
    top_brands: int = Query(20, ge=1, le=200, description="Limit to top N brands by product count"),
    db: AsyncSession = Depends(get_db),
):
    """Pivotable feed: (brand, store) → count + avg price. Frontend renders
    as a heatmap. Brand list trimmed to top N by overall product count to keep
    the matrix legible.
    """
    # Pick the top N brands first
    brand_count_stmt = (
        select(Product.brand, func.count(Product.id).label("cnt"))
        .where(Product.brand.isnot(None), Product.last_price.isnot(None))
        .group_by(Product.brand)
        .order_by(func.count(Product.id).desc())
        .limit(top_brands)
    )
    brand_rows = (await db.execute(brand_count_stmt)).all()
    if not brand_rows:
        return []
    keep_brands = {b for b, _ in brand_rows}

    cell_stmt = (
        select(
            Product.brand,
            Product.search_term.label("store"),
            func.count(Product.id).label("cnt"),
            func.avg(Product.last_price).label("avg_p"),
        )
        .where(
            Product.brand.in_(keep_brands),
            Product.last_price.isnot(None),
            Product.search_term.isnot(None),
        )
        .group_by(Product.brand, Product.search_term)
        .having(func.count(Product.id) >= min_count)
    )
    rows = (await db.execute(cell_stmt)).all()

    return [
        schemas.BrandStoreCell(
            brand=brand,
            store=(store or "unknown").capitalize(),
            product_count=int(cnt),
            avg_price=round(float(avg_p) if avg_p else 0.0, 2),
        )
        for brand, store, cnt, avg_p in rows
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 5. Volatility leaders
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/volatility", response_model=list[schemas.VolatilityItem])
async def volatility(
    window: Literal["24h", "7d", "30d"] = "30d",
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Top N products by price volatility (stddev) within the window. Requires
    at least 2 history observations; products that never moved show stddev=0
    and are filtered out.
    """
    days = _WINDOW_DAYS[window]
    cutoff = datetime.utcnow() - timedelta(days=days)

    vol_subq = (
        select(
            PriceHistory.product_id.label("pid"),
            func.stddev_samp(PriceHistory.price).label("vol"),
            func.max(PriceHistory.price).label("max_p"),
            func.min(PriceHistory.price).label("min_p"),
            func.count(PriceHistory.id).label("obs"),
        )
        .where(PriceHistory.parsed_at >= cutoff)
        .group_by(PriceHistory.product_id)
        .having(func.count(PriceHistory.id) >= 2)
        .subquery()
    )

    stmt = (
        select(Product, vol_subq.c.vol, vol_subq.c.max_p, vol_subq.c.min_p, vol_subq.c.obs)
        .join(vol_subq, vol_subq.c.pid == Product.id)
        .where(Product.last_price.isnot(None))
    )
    rows = (await db.execute(stmt)).all()

    items: list[schemas.VolatilityItem] = []
    for product, vol, max_p, min_p, obs in rows:
        vol_f = float(vol) if vol else 0.0
        rng = (float(max_p) - float(min_p)) if (max_p and min_p) else 0.0
        if vol_f < 0.01 and rng < 0.01:
            continue
        items.append(
            schemas.VolatilityItem(
                product_id=product.id,
                brand=product.brand,
                title=product.title,
                image_url=product.image_url,
                store_name=(product.search_term or "unknown").capitalize(),
                current_price=round(float(product.last_price), 2),
                volatility_eur=round(vol_f, 2),
                range_eur=round(rng, 2),
                observation_count=int(obs),
            )
        )

    items.sort(key=lambda v: v.volatility_eur, reverse=True)
    return items[:limit]


# ─────────────────────────────────────────────────────────────────────────────
# 6. Market trend — daily catalog-wide avg price
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/market-trend", response_model=list[schemas.MarketTrendPoint])
async def market_trend(
    window: Literal["7d", "30d", "90d"] = "30d",
    db: AsyncSession = Depends(get_db),
):
    """Daily average price across the entire catalog over the selected window.

    Sourced from PriceHistory (so includes all observations, not just current
    last_price). Used by the Overview chart on /analytics.
    """
    days = _WINDOW_DAYS[window]
    cutoff = datetime.utcnow() - timedelta(days=days)

    day = func.date_trunc("day", PriceHistory.parsed_at).label("d")
    stmt = (
        select(
            day,
            func.avg(PriceHistory.price).label("avg_p"),
            func.count(PriceHistory.id).label("obs"),
        )
        .where(
            PriceHistory.parsed_at >= cutoff,
            PriceHistory.price.isnot(None),
            PriceHistory.price > 0,
        )
        .group_by(day)
        .order_by(day.asc())
    )
    rows = (await db.execute(stmt)).all()

    return [
        schemas.MarketTrendPoint(
            date=d.date().isoformat(),
            avg_price=round(float(avg_p), 2),
            observation_count=int(obs),
        )
        for d, avg_p, obs in rows
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 7. Movers distribution — % change histogram
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/movers/distribution", response_model=list[schemas.MoversDistributionBin])
async def movers_distribution(
    window: Literal["24h", "7d", "30d"] = "7d",
    bin_size: int = Query(5, ge=1, le=20, description="Bin width in percent"),
    bin_max: int = Query(50, ge=10, le=100, description="Histogram half-range; symmetric around 0"),
    db: AsyncSession = Depends(get_db),
):
    """Distribution of % price changes within the window. Bins of `bin_size`%
    span symmetrically around zero from -bin_max..+bin_max. Outliers are clamped
    into the edge bins so the chart doesn't lose them.
    """
    days = _WINDOW_DAYS[window]
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Same earliest-in-window pattern as /movers
    ranked = (
        select(
            PriceHistory.product_id.label("pid"),
            PriceHistory.price.label("start_price"),
            func.row_number()
            .over(
                partition_by=PriceHistory.product_id,
                order_by=PriceHistory.parsed_at.asc(),
            )
            .label("rn"),
        )
        .where(PriceHistory.parsed_at >= cutoff)
        .subquery()
    )
    earliest = select(ranked.c.pid, ranked.c.start_price).where(ranked.c.rn == 1).subquery()

    stmt = (
        select(Product.last_price, earliest.c.start_price, Product.old_price)
        .outerjoin(earliest, earliest.c.pid == Product.id)
        .where(Product.last_price.isnot(None), Product.last_price > 0)
    )
    rows = (await db.execute(stmt)).all()

    # Build bins: [-50,-45), [-45,-40), ..., [-5,0), [0,5), ..., [45,50]
    bins: list[tuple[float, float, int]] = []
    edges = list(range(-bin_max, bin_max + 1, bin_size))
    for lo, hi in zip(edges[:-1], edges[1:]):
        bins.append((float(lo), float(hi), 0))

    if not bins:
        return []

    for last_p, hist_start, old_p in rows:
        start = hist_start if hist_start is not None else old_p
        if start is None or float(start) == 0:
            continue
        pct = (float(last_p) - float(start)) / float(start) * 100
        if abs(pct) < 0.05:
            continue
        # Clamp to histogram range
        if pct < bins[0][0]:
            idx = 0
        elif pct >= bins[-1][1]:
            idx = len(bins) - 1
        else:
            idx = int((pct - bins[0][0]) // bin_size)
            idx = max(0, min(len(bins) - 1, idx))
        lo, hi, cnt = bins[idx]
        bins[idx] = (lo, hi, cnt + 1)

    return [
        schemas.MoversDistributionBin(
            lower=lo,
            upper=hi,
            count=cnt,
            label=f"{int(lo):+d}..{int(hi):+d}%".replace("+0..+", "0..+").replace("-0..", "0.."),
        )
        for lo, hi, cnt in bins
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 8. Per-retailer trend — daily avg price per store
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/retailers/trend", response_model=list[schemas.RetailerTrendSeries])
async def retailers_trend(
    window: Literal["7d", "30d", "90d"] = "30d",
    db: AsyncSession = Depends(get_db),
):
    """Per-store daily avg price. Used to draw sparkline-style mini area charts
    next to each retailer row in the analytics page.
    """
    days = _WINDOW_DAYS[window]
    cutoff = datetime.utcnow() - timedelta(days=days)

    day = func.date_trunc("day", PriceHistory.parsed_at).label("d")
    stmt = (
        select(
            Product.search_term.label("store"),
            day,
            func.avg(PriceHistory.price).label("avg_p"),
        )
        .join(Product, Product.id == PriceHistory.product_id)
        .where(
            PriceHistory.parsed_at >= cutoff,
            PriceHistory.price.isnot(None),
            PriceHistory.price > 0,
            Product.search_term.isnot(None),
        )
        .group_by(Product.search_term, day)
        .order_by(Product.search_term.asc(), day.asc())
    )
    rows = (await db.execute(stmt)).all()

    by_store: dict[str, list[schemas.RetailerTrendPoint]] = {}
    for store, d, avg_p in rows:
        key = (store or "unknown").capitalize()
        by_store.setdefault(key, []).append(
            schemas.RetailerTrendPoint(date=d.date().isoformat(), avg_price=round(float(avg_p), 2))
        )

    return [schemas.RetailerTrendSeries(store=s, points=pts) for s, pts in by_store.items()]


# ─────────────────────────────────────────────────────────────────────────────
# Redesign: the Pro analytics cabinet. Synthetic gap-fill rows never count as
# price changes here; the price index draws them as an estimate.
# ─────────────────────────────────────────────────────────────────────────────
from app.api.cards import cards_for_keys  # noqa: E402
from app.services import market  # noqa: E402


@router.get("/overview", response_model=schemas.MarketSnapshot)
async def overview(db: AsyncSession = Depends(get_db)):
    """Market tonight: listings, comparable bottles, changes, who is cheapest."""
    return await market.snapshot(db)


@router.get("/activity", response_model=list[schemas.ActivityPoint])
async def activity(days: int = Query(30, ge=7, le=180), db: AsyncSession = Depends(get_db)):
    """Daily count of real price rises and cuts per shop."""
    return await market.activity(db, days)


@router.get("/price-index", response_model=schemas.PriceIndex)
async def price_index(days: int = Query(90, ge=14, le=180), db: AsyncSession = Depends(get_db)):
    """Same-basket price index per shop (100 = first day of the window)."""
    return await market.price_index(db, days)


@router.get("/moves", response_model=list[schemas.MoveItem])
async def moves(
    days: int = Query(7, ge=1, le=90),
    direction: Literal["down", "up"] = "down",
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Biggest moves of the same listing over the window."""
    return await market.moves(db, days=days, direction=direction, limit=limit)


@router.get("/gaps", response_model=list[schemas.GapRow])
async def gaps(
    limit: int = Query(20, ge=1, le=100),
    min_shops: int = Query(2, ge=2, le=5),
    db: AsyncSession = Depends(get_db),
):
    """Bottles with the widest gap between the cheapest and the dearest shop."""
    keys = await market.top_gap_keys(db, limit=limit, min_shops=min_shops)
    out = []
    for card in await cards_for_keys(db, keys):
        live = [o for o in card.offers if o.in_stock] or card.offers
        dear = max(live, key=lambda o: o.price)
        out.append(schemas.GapRow(
            card=card,
            gap_percent=round((dear.price - card.min_price) / card.min_price * 100, 1),
            gap_eur=round(dear.price - card.min_price, 2),
            dearest_store=dear.store,
        ))
    return out


@router.get("/brand-shop", response_model=schemas.BrandShopMatrix)
async def brand_shop(top: int = Query(12, ge=3, le=40), db: AsyncSession = Depends(get_db)):
    """Brand × shop: mean premium over the cheapest shop for the same bottles."""
    return await market.brand_shop(db, top)


@router.get("/distribution", response_model=list[schemas.DistributionBin])
async def distribution(days: int = Query(30, ge=7, le=90), db: AsyncSession = Depends(get_db)):
    """How far listings moved over the window, in 5% bins."""
    return await market.distribution(db, days)


@router.get("/price-bands", response_model=list[schemas.PriceBandRow])
async def price_bands(db: AsyncSession = Depends(get_db)):
    """In-stock listings per shop and price band."""
    return await market.price_bands(db)
