"""Market-wide figures: who is cheapest, how far apart shops are, recent drops.

Shared by the public landing teaser and the Pro analytics overview. The
synthetic gap-fill rows of October 2026 are left out of every count of price
changes and of the drops, so they never pass for real movements.
"""
from __future__ import annotations

import time
from types import SimpleNamespace
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import schemas
from app.services.price_series import HISTORY_START, STORE_LABELS, display_name, store_label

def _key_sql(t: str = "") -> str:
    """Card key (see app/api/cards.card_key_expr) as SQL, for table alias `t`."""
    a = f"{t}." if t else ""
    return (
        f"case when {a}group_id is not null then 'g' || {a}group_id || ':' || "
        f"coalesce(lower(replace({a}volume, ' ', '')), '') else 'p' || {a}id end"
    )


def _store_sql(t: str = "") -> str:
    a = f"{t}." if t else ""
    return f"replace(lower({a}search_term), '.lv', '')"


_KEY_SQL = _key_sql()
_STORE_SQL = _store_sql()

# Above this change, an old price read only once is taken for a misreading.
SINGLE_READING_MAX = 0.4
# Price index: a listing whose price leaves this band against day one is left out.
INDEX_RATIO_MIN, INDEX_RATIO_MAX = 0.5, 1.5

_CACHE: dict[str, tuple[float, object]] = {}
_TTL = 900


def _cached(name: str):
    hit = _CACHE.get(name)
    if hit and time.monotonic() - hit[0] < _TTL:
        return hit[1]
    return None


def _store(name: str, value):
    _CACHE[name] = (time.monotonic(), value)
    return value


async def snapshot(db: AsyncSession) -> schemas.MarketSnapshot:
    hit = _cached("snapshot")
    if hit is not None:
        return hit

    now = datetime.utcnow()
    week, month = now - timedelta(days=7), now - timedelta(days=30)

    per_shop = (await db.execute(text(f"""
        select {_STORE_SQL} as store,
               count(*) as products,
               count(*) filter (where is_available) as current,
               count(*) filter (where is_available and promo_price > 0) as promo
        from product where last_price > 0
        group by 1
    """))).all()

    changes = (await db.execute(text(f"""
        select {_store_sql('p')} as store,
               count(*) filter (where h.parsed_at >= :week) as c7,
               count(*) as c30
        from pricehistory h join product p on p.id = h.product_id
        where h.change_type in ('price_up', 'price_down') and h.parsed_at >= :month
        group by 1
    """), {"week": week, "month": month})).all()
    ch = {r.store: (int(r.c7), int(r.c30)) for r in changes}

    cmp_rows = (await db.execute(text(f"""
        with p as (
            select {_KEY_SQL} as key, {_STORE_SQL} as store, last_price as price
            from product where is_available and last_price > 0
        ),
        k as (
            select key, min(price) as lo, max(price) as hi
            from p group by key having count(distinct store) >= 2
        ),
        c as (
            select distinct on (p.key) p.key, p.store
            from p join k on k.key = p.key
            order by p.key, p.price, p.store
        )
        select c.store, count(*) as n,
               (select count(*) from k) as comparable,
               (select percentile_cont(0.5) within group (order by (hi - lo) / lo * 100) from k) as med,
               (select avg((hi - lo) / lo * 100) from k) as mean
        from c group by c.store
    """))).all()
    comparable = int(cmp_rows[0].comparable) if cmp_rows else 0
    cheapest = {r.store: int(r.n) for r in cmp_rows}
    med = float(cmp_rows[0].med or 0) if cmp_rows else 0.0
    mean = float(cmp_rows[0].mean or 0) if cmp_rows else 0.0

    hist = (await db.execute(text(
        "select count(*) as n, min(parsed_at) as since from pricehistory where change_type <> 'synthetic'"
    ))).one()
    as_of = (await db.execute(text("select max(last_seen) from product"))).scalar()

    order = list(STORE_LABELS)
    shops = []
    for r in sorted(per_shop, key=lambda r: order.index(r.store) if r.store in order else 99):
        c7, c30 = ch.get(r.store, (0, 0))
        n = cheapest.get(r.store, 0)
        shops.append(schemas.ShopSnapshot(
            store=r.store,
            store_name=store_label(r.store),
            products=int(r.products),
            current=int(r.current),
            changes_7d=c7,
            changes_30d=c30,
            cheapest_share=round(n / comparable * 100, 1) if comparable else 0.0,
            cheapest_count=n,
            promo_listings=int(r.promo),
        ))

    value = schemas.MarketSnapshot(
        as_of=as_of,
        total_products=sum(s.products for s in shops),
        current_products=sum(s.current for s in shops),
        comparable=comparable,
        changes_7d=sum(s.changes_7d for s in shops),
        changes_30d=sum(s.changes_30d for s in shops),
        history_rows=int(hist.n or 0),
        history_since=hist.since,
        spread_median=round(med, 1),
        spread_mean=round(mean, 1),
        shops=shops,
    )
    return _store("snapshot", value)


async def top_gap_keys(db: AsyncSession, limit: int = 6, min_shops: int = 2) -> list[str]:
    """Bottles with the widest % gap between the cheapest and dearest shop.

    Gaps over 150% are nearly always a mismatched pair (tester vs bottle,
    set vs single), so they are left out of the public list.
    """
    rows = (await db.execute(text(f"""
        with p as (
            select {_KEY_SQL} as key, {_STORE_SQL} as store, last_price as price, image_url
            from product where is_available and last_price > 15
        )
        select key, (max(price) - min(price)) / min(price) * 100 as gap
        from p group by key
        having count(distinct store) >= :min_shops and bool_or(image_url is not null)
           and (max(price) - min(price)) / min(price) * 100 <= 150
        order by gap desc limit :limit
    """), {"limit": limit, "min_shops": min_shops})).all()
    return [r.key for r in rows]


async def hero_key(db: AsyncSession) -> Optional[str]:
    """A widely sold bottle with a large euro gap, for the landing hero."""
    row = (await db.execute(text(f"""
        with p as (
            select {_KEY_SQL} as key, {_STORE_SQL} as store, last_price as price, image_url
            from product where is_available and last_price > 30
        )
        select key from p group by key
        having count(distinct store) >= 3 and bool_or(image_url is not null)
           and (max(price) - min(price)) / min(price) <= 1.0
        order by max(price) - min(price) desc limit 1
    """))).first()
    return row.key if row else None


async def shelf_keys(db: AsyncSession, limit: int = 4) -> list[str]:
    """Most watched bottles (favorites), topped up with the most widely sold.

    Returns twice `limit` keys so the caller can skip near-duplicates (the
    same perfume as EDP and Parfum).
    """
    rows = (await db.execute(text(f"""
        with p as (
            select pr.id, {_key_sql('pr')} as key, {_store_sql('pr')} as store, pr.image_url
            from product pr where pr.is_available and pr.last_price > 0
        )
        select p.key, count(distinct f.id) as fav, count(distinct p.store) as shops
        from p left join favorite f on f.product_id = p.id
        group by p.key
        having bool_or(p.image_url is not null) and count(distinct p.store) >= 3
        order by fav desc, shops desc, p.key limit :limit
    """), {"limit": limit * 2})).all()
    return [r.key for r in rows]


async def moves(
    db: AsyncSession,
    days: int = 30,
    direction: str = "down",
    limit: int = 6,
    stores: Optional[list[str]] = None,
    brands: Optional[list[str]] = None,
    min_price: float = 15.0,
    matched_only: bool = False,
    max_move: float = 0.7,
) -> list[schemas.MoveItem]:
    """Biggest real price moves: the same listing now versus `days` ago.

    Only listings with a real price change inside the window count, and moves
    beyond `max_move` are left out (almost always a re-matched or mislabeled
    listing). A move over 40% also needs the old price to have been seen twice
    in a row. `matched_only` keeps bottles that two or more shops sell, which
    filters out obscure sets and kits.
    """
    start = datetime.utcnow() - timedelta(days=days)
    down = direction == "down"
    where = ["p.is_available", "p.last_price > :min_price"]
    params: dict = {"start": start, "limit": limit * 4, "min_price": min_price}
    if stores:
        where.append(f"{_store_sql('p')} = any(:stores)")
        params["stores"] = [s.lower() for s in stores]
    if brands:
        # Substring match, like the catalogue: "Dior" also finds "Christian Dior".
        where.append("lower(p.brand) like any(:brands)")
        params["brands"] = [f"%{b.lower()}%" for b in brands]
    where.append("p.last_price < ref.price" if down else "p.last_price > ref.price")
    where.append("abs(p.last_price - ref.price) / ref.price < :max_move")
    params["max_move"] = max_move
    # A big move counts only from a price seen twice: a one-off reading (the
    # wrong size's price, fixed by the next scrape) is not a real old price.
    where.append(f"""(abs(p.last_price - ref.price) / ref.price < {SINGLE_READING_MAX}
        or abs(ref.price - ref.prev_price) / ref.price < {SINGLE_READING_MAX})""")
    if matched_only:
        where.append(f"""p.group_id in (
            select group_id from product where group_id is not null and is_available
            group by group_id having count(distinct {_STORE_SQL}) >= 2)""")
    rows = (await db.execute(text(f"""
        with seen as (
            select product_id, price, parsed_at,
                   lag(price) over (partition by product_id order by parsed_at) as prev_price
            from pricehistory
            where in_stock and price > 0 and change_type <> 'synthetic'
        ),
        ref as (
            select distinct on (product_id) product_id, price, prev_price
            from seen where parsed_at <= :start
            order by product_id, parsed_at desc
        ),
        last_move as (
            select product_id, max(parsed_at) as at from pricehistory
            where change_type = '{"price_down" if down else "price_up"}' and parsed_at > :start
            group by product_id
        )
        select p.id, p.search_term, p.brand, p.title, p.concentration, p.volume, p.image_url,
               p.group_id, ref.price as old_price, p.last_price as new_price, last_move.at as since,
               (p.last_price - ref.price) / ref.price * 100 as pct
        from product p
        join ref on ref.product_id = p.id
        join last_move on last_move.product_id = p.id
        where {' and '.join(where)}
        order by pct {"asc" if down else "desc"} limit :limit
    """), params)).all()

    out: list[schemas.MoveItem] = []
    seen: set = set()
    for r in rows:
        # One entry per bottle: the same perfume can move in two shops.
        k = (r.group_id or f"p{r.id}", (r.volume or "").lower())
        if k in seen:
            continue
        seen.add(k)
        store = (r.search_term or "").lower().replace(".lv", "")
        stand_in = SimpleNamespace(title=r.title or "", brand=r.brand, search_term=r.search_term)
        out.append(schemas.MoveItem(
            product_id=r.id,
            store=store,
            store_name=store_label(store),
            brand=(r.brand or "").strip(),
            name=display_name([stand_in]),
            concentration=r.concentration,
            volume=r.volume,
            image_url=r.image_url,
            old_price=float(r.old_price),
            new_price=float(r.new_price),
            change_percent=round(float(r.pct), 1),
            since=r.since,
        ))
        if len(out) >= limit:
            break
    return out


async def recent_drops(db: AsyncSession, days: int = 30, limit: int = 6, **kw) -> list[schemas.MoveItem]:
    return await moves(db, days=days, direction="down", limit=limit, **kw)


async def activity(db: AsyncSession, days: int = 30) -> list[schemas.ActivityPoint]:
    """Real price rises and cuts per shop and day (synthetic rows excluded)."""
    start = max(datetime.utcnow().date() - timedelta(days=days - 1), HISTORY_START)
    rows = (await db.execute(text(f"""
        select date(h.parsed_at) as d, {_store_sql('p')} as store,
               count(*) filter (where h.change_type = 'price_up') as up,
               count(*) filter (where h.change_type = 'price_down') as down
        from pricehistory h join product p on p.id = h.product_id
        where h.change_type in ('price_up', 'price_down') and h.parsed_at >= :start
        group by 1, 2 order by 1, 2
    """), {"start": datetime.combine(start, datetime.min.time())})).all()
    return [
        schemas.ActivityPoint(date=r.d.isoformat(), store=r.store, up=int(r.up), down=int(r.down))
        for r in rows
    ]


def _trimmed_mean(values: list[float], cut: float = 0.05) -> float:
    v = sorted(values)
    k = int(len(v) * cut)
    v = v[k: len(v) - k] or v
    return sum(v) / len(v)


async def price_index(db: AsyncSession, days: int = 90) -> schemas.PriceIndex:
    """Same-basket price index per shop, 100 on the first day of the window.

    Every listing that had a price on day one is followed with its
    forward-filled daily price; the shop's index is the 5%-trimmed mean of
    price/day-one-price, so a few mismatched listings cannot drag a whole
    shop, and a listing that halves or gains half is left out altogether.
    The window starts no earlier than October 7 (see HISTORY_START); the
    October 7-21 gap is drawn from the estimate rows.
    """
    key = f"index:{days}"
    hit = _cached(key)
    if hit is not None:
        return hit
    from app.services.price_series import day_range

    dates = day_range(days)
    last = dates[-1]
    rows = (await db.execute(text(f"""
        select h.product_id, h.price, h.in_stock, date(h.parsed_at) as d,
               {_store_sql('p')} as store, date(p.last_seen) as seen
        from pricehistory h join product p on p.id = h.product_id
        where p.last_price > 0
        order by h.product_id, h.parsed_at
    """))).all()

    n = len(dates)
    ratios: dict[str, list[list[float]]] = {}

    def flush(store: str, events: list, seen) -> None:
        # Forward-fill this listing over the window and add its ratios.
        i, cur, base = 0, None, None
        line: list[Optional[float]] = []
        for di, d in enumerate(dates):
            while i < len(events) and events[i][0] <= d:
                cur = events[i][1]
                i += 1
            if seen and (d - seen).days > 3:
                cur = None
            if di == 0:
                base = cur
                if not base:
                    return
            line.append(cur / base if cur else None)
        # Halving or +50% inside the window is a parser fix or a wrong size,
        # not the market: such a listing stays out of the basket.
        if any(x is not None and not INDEX_RATIO_MIN <= x <= INDEX_RATIO_MAX for x in line):
            return
        r = ratios.setdefault(store, [[] for _ in range(n)])
        for di, x in enumerate(line):
            if x is not None:
                r[di].append(x)

    pid, store, seen, events = None, None, None, []
    for r in rows:
        if r.product_id != pid:
            if pid is not None and events:
                flush(store, events, seen)
            pid, store, seen, events = r.product_id, r.store, r.seen, []
        if r.d <= last:
            events.append((r.d, float(r.price) if r.in_stock and r.price else None))
    if pid is not None and events:
        flush(store, events, seen)

    order = list(STORE_LABELS)
    shops = {}
    basket = {}
    for st in sorted(ratios, key=lambda k: order.index(k) if k in order else 99):
        days_r = ratios[st]
        if not days_r[0]:
            continue
        shops[st] = [round(_trimmed_mean(v) * 100, 2) if v else None for v in days_r]
        basket[st] = len(days_r[0])
    value = schemas.PriceIndex(days=[d.isoformat() for d in dates], shops=shops, basket=basket,
                               estimated_from="2026-10-07", estimated_to="2026-10-21")
    return _store(key, value)


async def brand_shop(db: AsyncSession, top: int = 12) -> schemas.BrandShopMatrix:
    """How much more each shop asks than the cheapest shop, per brand.

    Over bottles in stock in two or more shops: the mean of
    (shop price - cheapest price) / cheapest price, per brand and shop.
    """
    hit = _cached(f"brand_shop:{top}")
    if hit is not None:
        return hit
    rows = (await db.execute(text(f"""
        with p as (
            select {_KEY_SQL} as key, {_STORE_SQL} as store, lower(trim(brand)) as b, trim(brand) as label,
                   last_price as price
            from product where is_available and last_price > 0 and brand is not null and brand <> ''
        ),
        k as (select key, min(price) as lo from p group by key having count(distinct store) >= 2),
        top_b as (
            select p.b, count(distinct p.key) as n from p join k on k.key = p.key
            group by p.b order by n desc limit :top
        )
        select p.b, p.store, mode() within group (order by p.label) as label,
               avg((p.price - k.lo) / k.lo * 100) as premium,
               count(distinct p.key) as bottles,
               (select n from top_b where top_b.b = p.b) as total
        from p join k on k.key = p.key join top_b on top_b.b = p.b
        group by p.b, p.store
        order by total desc, p.b, p.store
    """), {"top": top})).all()
    labels: dict[str, str] = {}
    for r in rows:
        # Prefer a non-shouting spelling ("Dior" over "DIOR").
        cur = labels.get(r.b)
        if cur is None or (cur == cur.upper() and r.label != r.label.upper()):
            labels[r.b] = r.label
    brands = list(dict.fromkeys(r.b for r in rows))
    order = list(STORE_LABELS)
    stores = sorted({r.store for r in rows}, key=lambda k: order.index(k) if k in order else 99)
    value = schemas.BrandShopMatrix(
        brands=[labels[b] for b in brands],
        stores=stores,
        cells=[
            schemas.BrandShopCell(brand=labels[r.b], store=r.store, premium=round(float(r.premium), 1),
                                  bottles=int(r.bottles))
            for r in rows
        ],
    )
    return _store(f"brand_shop:{top}", value)


async def distribution(db: AsyncSession, days: int = 30, step: int = 5, edge: int = 40) -> list[schemas.DistributionBin]:
    """How far listings moved over the window: % change against the window
    start, for listings whose price changed. Outliers sit in the edge bins."""
    start = datetime.utcnow() - timedelta(days=days)
    rows = (await db.execute(text("""
        with ref as (
            select distinct on (product_id) product_id, price
            from pricehistory
            where parsed_at <= :start and in_stock and price > 0
            order by product_id, parsed_at desc
        )
        select (p.last_price - ref.price) / ref.price * 100 as pct
        from product p join ref on ref.product_id = p.id
        where p.is_available and p.last_price > 0 and abs(p.last_price - ref.price) >= 0.01
    """), {"start": start})).all()
    edges = list(range(-edge, edge + 1, step))
    bins = [[lo, lo + step, 0] for lo in edges[:-1]]
    for (pct,) in rows:
        v = float(pct)
        i = 0 if v < -edge else len(bins) - 1 if v >= edge else int((v + edge) // step)
        bins[max(0, min(len(bins) - 1, i))][2] += 1
    return [schemas.DistributionBin(lower=lo, upper=hi, count=c) for lo, hi, c in bins]


PRICE_BANDS = [(0, 25), (25, 50), (50, 75), (75, 100), (100, 150), (150, 200), (200, None)]


async def price_bands(db: AsyncSession) -> list[schemas.PriceBandRow]:
    """In-stock listings per shop and price band: where each shop's range sits."""
    cases = " ".join(
        f"when last_price >= {lo}" + (f" and last_price < {hi}" if hi else "") + f" then {i}"
        for i, (lo, hi) in enumerate(PRICE_BANDS)
    )
    rows = (await db.execute(text(f"""
        select {_STORE_SQL} as store, case {cases} end as band, count(*) as n
        from product where is_available and last_price > 0
        group by 1, 2
    """))).all()
    out = []
    for r in rows:
        lo, hi = PRICE_BANDS[int(r.band)]
        out.append(schemas.PriceBandRow(store=r.store, band=int(r.band),
                                        label=f"€{lo}–{hi}" if hi else f"€{lo}+", count=int(r.n)))
    order = list(STORE_LABELS)
    out.sort(key=lambda b: (order.index(b.store) if b.store in order else 99, b.band))
    return out
