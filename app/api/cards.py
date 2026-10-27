"""Catalogue for the redesign: perfume cards, shop listings and filter facets.

A card is one perfume in one size: every product of the same ProductGroup with
the same volume, one offer per shop listing. Products without a group get a
card of their own. The shop and in-stock filters decide which offers a card
shows, so a card is painted in the cheapest of the shops the user picked.
"""
from __future__ import annotations

import re
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, case, cast, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import schemas
from app.api.catalog_filters import apply_product_filters
from app.api.deps import get_current_user, get_db
from app.domain.models import Favorite, PriceHistory, Product
from app.services import market
from app.services.price_series import display_image, display_name, store_key, store_label

router = APIRouter(prefix="/products", tags=["catalogue"], dependencies=[Depends(get_current_user)])

CHANGE_WINDOW_DAYS = 30


# Both expressions are built from literal_column() rather than bound
# parameters: Postgres matches GROUP BY against the SELECT list textually, and
# two sets of bind parameters would make the same expression look different.

def card_key_expr():
    """SQL expression for the card a product belongs to."""
    vol = func.coalesce(func.lower(func.replace(Product.volume, literal_column("' '"), literal_column("''"))), literal_column("''"))
    return case(
        (
            Product.group_id.isnot(None),
            literal_column("'g'") + cast(Product.group_id, String) + literal_column("':'") + vol,
        ),
        else_=literal_column("'p'") + cast(Product.id, String),
    )


def store_expr():
    return func.replace(func.lower(Product.search_term), literal_column("'.lv'"), literal_column("''"))


def card_key(p: Product) -> str:
    if p.group_id is not None:
        return f"g{p.group_id}:{(p.volume or '').replace(' ', '').lower()}"
    return f"p{p.id}"


def ref_price_subquery(days: int = CHANGE_WINDOW_DAYS):
    """(pid, ref_price): the price at the start of the window, or the first
    price inside it for bottles listed later."""
    start = datetime.utcnow() - timedelta(days=days)
    before = (
        select(PriceHistory.product_id.label("pid"), PriceHistory.price.label("price"))
        .where(PriceHistory.parsed_at <= start, PriceHistory.in_stock.is_(True), PriceHistory.price > 0)
        .distinct(PriceHistory.product_id)
        .order_by(PriceHistory.product_id, PriceHistory.parsed_at.desc())
        .subquery()
    )
    first = (
        select(PriceHistory.product_id.label("pid"), PriceHistory.price.label("price"))
        .where(PriceHistory.parsed_at > start, PriceHistory.in_stock.is_(True), PriceHistory.price > 0)
        .distinct(PriceHistory.product_id)
        .order_by(PriceHistory.product_id, PriceHistory.parsed_at.asc())
        .subquery()
    )
    # MATERIALIZED: computed once per query. Inlined, the planner misjudges a
    # filtered catalogue as one row and re-runs both DISTINCT ONs per product.
    return (
        select(Product.id.label("pid"), func.coalesce(before.c.price, first.c.price).label("ref_price"))
        .outerjoin(before, before.c.pid == Product.id)
        .outerjoin(first, first.c.pid == Product.id)
        .cte("ref_price")
        .prefix_with("MATERIALIZED", dialect="postgresql")
    )


def _pct(now: Optional[float], ref: Optional[float]) -> Optional[float]:
    if now is None or not ref:
        return None
    return round((float(now) - float(ref)) / float(ref) * 100, 1)


def _f(v) -> Optional[float]:
    return float(v) if v is not None else None


# Houses most shoppers know by name. A perfume from one of them ranks higher in
# the "popular" order, which the catalogue opens with.
POPULAR_BRANDS = (
    "dior", "chanel", "yves saint laurent", "giorgio armani", "armani", "hugo boss", "boss",
    "versace", "paco rabanne", "rabanne", "jean paul gaultier", "dolce & gabbana",
    "carolina herrera", "lancôme", "lancome", "guerlain", "givenchy", "tom ford", "creed",
    "prada", "gucci", "burberry", "calvin klein", "montblanc", "azzaro", "valentino",
    "viktor & rolf", "mugler", "narciso rodriguez", "kenzo", "hermès", "hermes", "chloé",
    "chloe", "marc jacobs", "lacoste", "davidoff", "maison francis kurkdjian",
    "parfums de marly", "initio", "xerjoff", "byredo", "le labo", "jo malone",
    "zadig & voltaire", "ralph lauren", "bvlgari", "cartier", "jimmy choo", "lattafa",
)


def favorites_subquery():
    """(pid, n): how many users saved each product."""
    return select(Favorite.product_id.label("pid"), func.count().label("n")).group_by(Favorite.product_id).subquery()


def popularity(shops, brand_lower, favs, in_stock):
    """Sold in many shops, a known house, saved by users, in stock now."""
    return (
        shops * 10
        + case((brand_lower.in_(POPULAR_BRANDS), 8), else_=0)
        + func.least(func.coalesce(favs, 0), 6) * 4
        + case((in_stock, 3), else_=0)
    )


CardSort = Literal["popular", "shops", "drop", "low", "high", "gap", "brand", "new"]


async def query_cards(
    db: AsyncSession,
    *,
    search: Optional[str] = None,
    brands: Optional[List[str]] = None,
    stores: Optional[List[str]] = None,
    volumes: Optional[List[str]] = None,
    types: Optional[List[str]] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    in_stock: Optional[bool] = None,
    promo: Optional[bool] = None,
    multi_shop: Optional[bool] = None,
    dropped: Optional[bool] = None,
    ids: Optional[List[int]] = None,
    sort: CardSort = "popular",
    skip: int = 0,
    limit: int = 24,
) -> schemas.CardsPage:
    key = card_key_expr().label("key")
    ref = ref_price_subquery()
    favs = favorites_subquery()
    price_live = case((Product.is_available.is_(True), Product.last_price))

    base = select(
        key,
        Product.id.label("id"),
        Product.last_price.label("price"),
        price_live.label("price_live"),
        ref.c.ref_price.label("ref_price"),
        store_expr().label("store"),
        Product.brand.label("brand"),
        Product.title.label("title"),
        Product.created_at.label("created_at"),
        Product.promo_price.label("promo_price"),
        func.coalesce(favs.c.n, 0).label("favs"),
    ).outerjoin(ref, ref.c.pid == Product.id).outerjoin(favs, favs.c.pid == Product.id).where(Product.last_price > 0)
    base = apply_product_filters(
        base, search=search, brands=brands, stores=stores, volumes=volumes, types=types,
        price_min=price_min, price_max=price_max, in_stock=in_stock, promo=promo, ids=ids,
    ).subquery()

    min_now = func.coalesce(func.min(base.c.price_live), func.min(base.c.price))
    min_ref = func.min(base.c.ref_price)
    agg = select(
        base.c.key,
        min_now.label("min_price"),
        func.max(base.c.price).label("max_price"),
        func.count(func.distinct(base.c.store)).label("shops"),
        func.count(base.c.id).label("offers"),
        min_ref.label("min_ref"),
        func.min(func.lower(base.c.brand)).label("brand_sort"),
        func.min(func.lower(base.c.title)).label("title_sort"),
        func.min(base.c.created_at).label("first_seen"),
        func.sum(base.c.favs).label("favs"),
        func.count(base.c.price_live).label("live"),
    ).group_by(base.c.key)
    if multi_shop:
        agg = agg.having(func.count(func.distinct(base.c.store)) >= 2)
    if dropped:
        agg = agg.having(min_now < min_ref)
    agg = agg.subquery()

    totals = (await db.execute(select(func.count(), func.coalesce(func.sum(agg.c.offers), 0)).select_from(agg))).one()

    change = (agg.c.min_price - agg.c.min_ref) / func.nullif(agg.c.min_ref, 0)
    gap = (agg.c.max_price - agg.c.min_price) / func.nullif(agg.c.min_price, 0)
    order = {
        # md5 spreads equal scores across brands instead of listing them A–Z.
        "popular": [popularity(agg.c.shops, agg.c.brand_sort, agg.c.favs, agg.c.live > 0).desc(), func.md5(agg.c.key)],
        "shops": [agg.c.shops.desc(), agg.c.offers.desc(), agg.c.brand_sort, agg.c.title_sort],
        "drop": [change.asc().nulls_last(), agg.c.shops.desc()],
        "low": [agg.c.min_price.asc(), agg.c.title_sort],
        "high": [agg.c.min_price.desc(), agg.c.title_sort],
        # Gaps inside one shop (two listings of the same bottle) come last.
        "gap": [case((agg.c.shops >= 2, gap)).desc().nulls_last(), agg.c.shops.desc()],
        "brand": [agg.c.brand_sort, agg.c.title_sort],
        "new": [agg.c.first_seen.desc(), agg.c.title_sort],
    }[sort]
    page_rows = (
        await db.execute(select(agg.c.key, agg.c.min_ref).order_by(*order, agg.c.key).offset(skip).limit(limit))
    ).all()
    keys = [r.key for r in page_rows]
    if not keys:
        return schemas.CardsPage(total=int(totals[0] or 0), listings=int(totals[1] or 0), items=[])

    prod_stmt = apply_product_filters(
        select(Product, ref.c.ref_price).outerjoin(ref, ref.c.pid == Product.id).where(
            Product.last_price > 0, card_key_expr().in_(keys)
        ),
        search=search, brands=brands, stores=stores, volumes=volumes, types=types,
        price_min=price_min, price_max=price_max, in_stock=in_stock, promo=promo, ids=ids,
    )
    grouped: dict[str, list[tuple[Product, Optional[float]]]] = defaultdict(list)
    for p, ref_price in (await db.execute(prod_stmt)).all():
        grouped[card_key(p)].append((p, _f(ref_price)))

    items: list[schemas.CatalogCard] = []
    for k in keys:
        rows = grouped.get(k)
        if not rows:
            continue
        items.append(build_card(k, rows))
    return schemas.CardsPage(total=int(totals[0] or 0), listings=int(totals[1] or 0), items=items)


def build_card(key: str, rows: list[tuple[Product, Optional[float]]]) -> schemas.CatalogCard:
    products = [p for p, _ in rows]
    offers = []
    for p, ref_price in rows:
        offers.append(schemas.CardOffer(
            product_id=p.id,
            store=store_key(p.search_term),
            store_name=store_label(store_key(p.search_term)),
            title=p.title,
            price=float(p.last_price),
            old_price=_f(p.old_price),
            promo_price=_f(p.promo_price),
            promo_code=p.promo_code,
            url=p.url,
            in_stock=p.is_available,
            checked_at=p.last_seen,
            change_30d=_pct(p.last_price, ref_price),
        ))
    live = [o for o in offers if o.in_stock] or offers
    live.sort(key=lambda o: o.price)
    offers.sort(key=lambda o: (not o.in_stock, o.price))
    best = live[0]
    refs = [r for _, r in rows if r]
    best_ref = min(refs) if refs else None
    concs = [p.concentration for p in products if p.concentration]
    return schemas.CatalogCard(
        key=key,
        product_id=best.product_id,
        brand=(products[0].brand or "").strip() or "—",
        name=display_name(products),
        concentration=max(set(concs), key=concs.count) if concs else None,
        volume=products[0].volume,
        image_url=display_image(products),
        min_price=best.price,
        max_price=max(o.price for o in offers),
        cheapest_store=best.store,
        shops=len({o.store for o in offers}),
        change_30d=_pct(best.price, best_ref),
        has_promo=any(o.promo_price for o in offers),
        offers=offers,
    )


@router.get("/cards", response_model=schemas.CardsPage)
async def get_cards(
    search: Optional[str] = None,
    brands: List[str] = Query(None),
    stores: List[str] = Query(None),
    volumes: List[str] = Query(None),
    types: List[str] = Query(None),
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    in_stock: Optional[bool] = None,
    promo: Optional[bool] = None,
    multi_shop: Optional[bool] = None,
    dropped: Optional[bool] = None,
    sort: CardSort = "popular",
    skip: int = Query(0, ge=0),
    limit: int = Query(24, ge=1, le=96),
    db: AsyncSession = Depends(get_db),
):
    """Perfume cards for the catalogue grid and the Today page."""
    return await query_cards(
        db, search=search, brands=brands, stores=stores, volumes=volumes, types=types,
        price_min=price_min, price_max=price_max, in_stock=in_stock, promo=promo,
        multi_shop=multi_shop, dropped=dropped, sort=sort, skip=skip, limit=limit,
    )


ListingSort = Literal["popular", "brand", "name", "price", "change", "shop"]

_VOLUME_TAIL = re.compile(r"\s+\d+(?:[.,]\d+)?\s?(?:ml|g)\b.*$", re.IGNORECASE)


def listing_name(p: Product) -> str:
    title = (p.title or "").strip()
    brand = (p.brand or "").strip()
    if brand and title.lower().startswith(brand.lower()):
        title = title[len(brand):].strip(" -·")
    return _VOLUME_TAIL.sub("", title).strip() or (p.title or "")


async def query_listings(
    db: AsyncSession,
    *,
    sort: ListingSort = "popular",
    direction: Literal["asc", "desc"] = "asc",
    skip: int = 0,
    limit: int = 50,
    multi_shop: Optional[bool] = None,
    dropped: Optional[bool] = None,
    **filters,
) -> schemas.ListingsPage:
    ref = ref_price_subquery()
    stmt = select(Product, ref.c.ref_price).outerjoin(ref, ref.c.pid == Product.id).where(Product.last_price > 0)
    stmt = apply_product_filters(stmt, **filters)
    if dropped:
        stmt = stmt.where(ref.c.ref_price.isnot(None), Product.last_price < ref.c.ref_price)
    if multi_shop:
        key = card_key_expr()
        multi = (
            select(card_key_expr().label("k"))
            .where(Product.last_price > 0)
            .group_by(card_key_expr())
            .having(func.count(func.distinct(store_expr())) >= 2)
            .subquery()
        )
        stmt = stmt.where(key.in_(select(multi.c.k)))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    change = (Product.last_price - ref.c.ref_price) / func.nullif(ref.c.ref_price, 0)
    if sort == "popular":
        shops_per_card = (
            select(card_key_expr().label("k"), func.count(func.distinct(store_expr())).label("s"))
            .where(Product.last_price > 0)
            .group_by(card_key_expr())
            .subquery()
        )
        favs = favorites_subquery()
        stmt = stmt.outerjoin(shops_per_card, shops_per_card.c.k == card_key_expr()).outerjoin(favs, favs.c.pid == Product.id)
        score = popularity(func.coalesce(shops_per_card.c.s, 1), func.lower(Product.brand), favs.c.n, Product.is_available.is_(True))
        rows = (await db.execute(stmt.order_by(score.desc(), func.md5(cast(Product.id, String))).offset(skip).limit(limit))).all()
    else:
        col = {
            "brand": [func.lower(Product.brand), func.lower(Product.title)],
            "name": [func.lower(Product.title)],
            "price": [Product.last_price],
            "change": [change],
            "shop": [store_expr(), Product.last_price],
        }[sort]
        order = [c.desc().nulls_last() if direction == "desc" else c.asc().nulls_last() for c in col]
        rows = (await db.execute(stmt.order_by(*order, Product.id).offset(skip).limit(limit))).all()
    items = [
        schemas.ListingRow(
            product_id=p.id,
            brand=(p.brand or "").strip() or "—",
            name=listing_name(p),
            title=p.title,
            volume=p.volume,
            concentration=p.concentration,
            image_url=p.image_url,
            price=float(p.last_price),
            old_price=_f(p.old_price),
            promo_price=_f(p.promo_price),
            promo_code=p.promo_code,
            change_30d=_pct(p.last_price, ref_price),
            store=store_key(p.search_term),
            store_name=store_label(store_key(p.search_term)),
            in_stock=p.is_available,
            url=p.url,
            checked_at=p.last_seen,
        )
        for p, ref_price in rows
    ]
    return schemas.ListingsPage(total=int(total or 0), items=items)


@router.get("/listings", response_model=schemas.ListingsPage)
async def get_listings(
    search: Optional[str] = None,
    brands: List[str] = Query(None),
    stores: List[str] = Query(None),
    volumes: List[str] = Query(None),
    types: List[str] = Query(None),
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    in_stock: Optional[bool] = None,
    promo: Optional[bool] = None,
    multi_shop: Optional[bool] = None,
    dropped: Optional[bool] = None,
    sort: ListingSort = "popular",
    direction: Literal["asc", "desc"] = "asc",
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """One row per shop listing, for the catalogue's table view."""
    return await query_listings(
        db, sort=sort, direction=direction, skip=skip, limit=limit,
        multi_shop=multi_shop, dropped=dropped,
        search=search, brands=brands, stores=stores, volumes=volumes, types=types,
        price_min=price_min, price_max=price_max, in_stock=in_stock, promo=promo,
    )


@router.get("/drops", response_model=List[schemas.MoveItem])
async def get_drops(
    days: int = Query(7, ge=1, le=60),
    stores: List[str] = Query(None),
    brands: List[str] = Query(None),
    limit: int = Query(12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Biggest recent price cuts, optionally in the user's shops and brands.
    Feeds the Today page."""
    return await market.moves(db, days=days, direction="down", limit=limit, stores=stores, brands=brands,
                              min_price=10.0, max_move=0.6)


_FACETS_CACHE: dict = {"at": 0.0, "value": None}
_FACETS_TTL = 600

_CONC_ORDER = ["EDP", "EDT", "Parfum", "EDC"]


def _ml(v: str) -> float:
    m = re.search(r"(\d+(?:[.,]\d+)?)", v or "")
    return float(m.group(1).replace(",", ".")) if m else 0.0


@router.get("/filters", response_model=schemas.CatalogFacets)
async def get_filters(db: AsyncSession = Depends(get_db)):
    """Every value the catalogue filters can take, with product counts."""
    now = time.monotonic()
    if _FACETS_CACHE["value"] is not None and now - _FACETS_CACHE["at"] < _FACETS_TTL:
        return _FACETS_CACHE["value"]

    priced = Product.last_price > 0
    stores = (await db.execute(
        select(store_expr(), func.count()).where(priced).group_by(store_expr())
    )).all()
    concs = (await db.execute(
        select(Product.concentration, func.count()).where(priced).group_by(Product.concentration)
    )).all()
    vols = (await db.execute(
        select(Product.volume, func.count()).where(priced, Product.volume.isnot(None), Product.volume != "")
        .group_by(Product.volume)
    )).all()
    brands = (await db.execute(
        select(Product.brand, func.count()).where(priced, Product.brand.isnot(None), Product.brand != "")
        .group_by(Product.brand)
    )).all()
    lo, hi, as_of = (await db.execute(
        select(func.min(Product.last_price), func.max(Product.last_price), func.max(Product.last_seen)).where(priced)
    )).one()

    conc_counts: dict[str, int] = defaultdict(int)
    for value, count in concs:
        label = next((c for c in _CONC_ORDER if (value or "").lower() == c.lower()), None)
        conc_counts[label or "other"] += int(count)
    conc_facets = [
        schemas.FacetValue(value=c, label=c if c != "other" else "Other", count=conc_counts[c])
        for c in _CONC_ORDER + ["other"] if conc_counts.get(c)
    ]

    # Brands come cased differently per shop (DIOR, Dior): merge them and
    # label each with its most common spelling.
    merged: dict[str, dict[str, int]] = defaultdict(dict)
    for name, count in brands:
        merged[name.strip().lower()][name.strip()] = merged[name.strip().lower()].get(name.strip(), 0) + int(count)
    brand_facets = []
    for spellings in merged.values():
        label = max(spellings.items(), key=lambda kv: (kv[0] != kv[0].upper(), kv[1]))[0]
        brand_facets.append(schemas.FacetValue(value=label, label=label, count=sum(spellings.values())))
    brand_facets.sort(key=lambda f: (-f.count, f.label.lower()))

    value = schemas.CatalogFacets(
        stores=[
            schemas.FacetValue(value=k, label=store_label(k), count=int(c))
            for k, c in sorted(stores, key=lambda r: -r[1])
        ],
        concentrations=conc_facets,
        volumes=[
            schemas.FacetValue(value=v, label=v.replace("ml", " ml"), count=int(c))
            for v, c in sorted(vols, key=lambda r: (_ml(r[0]), r[0]))
        ],
        brands=brand_facets,
        price_min=float(lo or 0),
        price_max=float(hi or 0),
        as_of=as_of,
    )
    _FACETS_CACHE.update(at=now, value=value)
    return value


async def cards_for_keys(db: AsyncSession, keys: List[str]) -> list[schemas.CatalogCard]:
    """Cards for the given keys, in that order, with every priced offer."""
    if not keys:
        return []
    ref = ref_price_subquery()
    stmt = select(Product, ref.c.ref_price).outerjoin(ref, ref.c.pid == Product.id).where(
        Product.last_price > 0, card_key_expr().in_(keys)
    )
    grouped: dict[str, list[tuple[Product, Optional[float]]]] = defaultdict(list)
    for p, ref_price in (await db.execute(stmt)).all():
        grouped[card_key(p)].append((p, _f(ref_price)))
    return [build_card(k, grouped[k]) for k in keys if grouped.get(k)]
