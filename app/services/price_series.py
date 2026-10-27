"""Daily price series built from the sparse PriceHistory event log.

PriceHistory stores one row per observed change (initial, price_up,
price_down, out_of_stock, back_in_stock) plus the synthetic gap-fill rows of
October 2026. To draw a chart or measure a 30-day change we need the price on
every day, so each product's events are forward-filled: the price on a day is
the last price seen on or before that day, and None while the bottle is out of
stock or before the shop first listed it.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Iterable, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import PriceHistory, Product

# A product the scraper has not seen for this long stops drawing a line.
STALE_AFTER_DAYS = 3

# Order in which shops lend their title and photo to a grouped card: Notino and
# Makeup photos sit on white and their titles are not upper-cased.
_DISPLAY_PRIORITY = ["notino", "makeup", "douglas", "220", "1a"]

_VOLUME_TAIL = re.compile(r"\s+\d+(?:[.,]\d+)?\s?(?:ml|g)\b.*$", re.IGNORECASE)


def store_key(search_term: Optional[str]) -> str:
    """'makeup.lv' -> 'makeup', 'Douglas Latvia' -> 'douglas'."""
    s = (search_term or "").lower().strip()
    for suffix in (".lv", " latvija", " latvia"):
        if s.endswith(suffix):
            return s[: -len(suffix)].strip()
    return s


STORE_LABELS = {
    "notino": "Notino",
    "makeup": "Makeup.lv",
    "220": "220.lv",
    "douglas": "Douglas",
    "1a": "1a.lv",
}


def store_label(key: str) -> str:
    return STORE_LABELS.get(key, key)


def _display_rank(p: Product) -> int:
    key = store_key(p.search_term)
    return _DISPLAY_PRIORITY.index(key) if key in _DISPLAY_PRIORITY else len(_DISPLAY_PRIORITY)


def display_name(products: Sequence[Product]) -> str:
    """Perfume name without the brand prefix and the trailing volume.

    Douglas titles are upper-cased, so another shop's spelling wins when the
    card has one.
    """
    ordered = sorted(products, key=lambda p: (p.title == p.title.upper(), _display_rank(p)))
    p = ordered[0]
    title = (p.title or "").strip()
    brand = (p.brand or "").strip()
    if brand and title.lower().startswith(brand.lower()):
        title = title[len(brand):].strip(" -·")
    title = _VOLUME_TAIL.sub("", title).strip()
    return title or (p.title or "").strip()


def display_image(products: Sequence[Product]) -> Optional[str]:
    for p in sorted(products, key=_display_rank):
        if p.image_url:
            return p.image_url
    return None


def day_range(days: int, end: Optional[date] = None) -> list[date]:
    end = end or datetime.utcnow().date()
    start = end - timedelta(days=days - 1)
    return [start + timedelta(days=i) for i in range(days)]


async def product_series(
    db: AsyncSession,
    products: Iterable[Product],
    days: list[date],
) -> dict[int, list[Optional[float]]]:
    """Forward-filled daily price for each product over `days`."""
    products = list(products)
    if not products or not days:
        return {}
    ids = [p.id for p in products]
    end_dt = datetime.combine(days[-1] + timedelta(days=1), datetime.min.time())
    rows = (
        await db.execute(
            select(PriceHistory.product_id, PriceHistory.price, PriceHistory.in_stock, PriceHistory.parsed_at)
            .where(PriceHistory.product_id.in_(ids), PriceHistory.parsed_at < end_dt)
            .order_by(PriceHistory.product_id, PriceHistory.parsed_at)
        )
    ).all()
    events: dict[int, list[tuple[date, Optional[float]]]] = defaultdict(list)
    for pid, price, in_stock, parsed_at in rows:
        events[pid].append((parsed_at.date(), float(price) if in_stock and price else None))

    out: dict[int, list[Optional[float]]] = {}
    for p in products:
        evs = events.get(p.id, [])
        last_seen = p.last_seen.date() if p.last_seen else None
        series: list[Optional[float]] = []
        i, cur, started = 0, None, False
        for d in days:
            while i < len(evs) and evs[i][0] <= d:
                cur, started = evs[i][1], True
                i += 1
            if not started or (last_seen and (d - last_seen).days > STALE_AFTER_DAYS):
                series.append(None)
            else:
                series.append(cur)
        # The scraper's current price is the truth for today even when the
        # last event is older or missing (products scraped before history).
        if p.is_available and p.last_price and float(p.last_price) > 0 and (
            not last_seen or (days[-1] - last_seen).days <= STALE_AFTER_DAYS
        ):
            series[-1] = float(p.last_price)
        out[p.id] = series
    return out


def by_store(
    products: Iterable[Product],
    series: dict[int, list[Optional[float]]],
) -> dict[str, list[Optional[float]]]:
    """Cheapest daily price per shop across the given products."""
    out: dict[str, list[Optional[float]]] = {}
    for p in products:
        s = series.get(p.id)
        if not s:
            continue
        key = store_key(p.search_term)
        if key not in out:
            out[key] = list(s)
            continue
        merged = out[key]
        for i, v in enumerate(s):
            if v is not None and (merged[i] is None or v < merged[i]):
                merged[i] = v
    return out


def cheapest_line(store_series: dict[str, list[Optional[float]]]) -> list[Optional[float]]:
    lines = list(store_series.values())
    if not lines:
        return []
    n = len(lines[0])
    out: list[Optional[float]] = []
    for i in range(n):
        vals = [line[i] for line in lines if line[i] is not None]
        out.append(min(vals) if vals else None)
    return out


def cheapest_shop_by_day(store_series: dict[str, list[Optional[float]]]) -> list[Optional[str]]:
    if not store_series:
        return []
    n = len(next(iter(store_series.values())))
    out: list[Optional[str]] = []
    for i in range(n):
        best_key, best = None, None
        for key, line in store_series.items():
            v = line[i]
            if v is not None and (best is None or v < best):
                best_key, best = key, v
        out.append(best_key)
    return out


def change_percent(line: list[Optional[float]], days: int) -> Optional[float]:
    """Change of the last value against the first known value in the window."""
    if not line or line[-1] is None:
        return None
    now = line[-1]
    for v in line[max(0, len(line) - 1 - days): len(line) - 1]:
        if v is not None and v > 0:
            return round((now - v) / v * 100, 1)
    return None
