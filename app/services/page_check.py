"""Read listings again on the shop's own product page.

The catalogue pass reads prices from listing pages. Before a deal reaches
Today it is opened on the shop's product page, the page a visitor lands on:
a deal is shown only when that page confirmed today's price and stock. When
the page disagrees, the listing is corrected to the page (the page is what a
buyer sees). A few random listings of each pass are read the same way as a
daily audit; the admin panel shows the results (PageCheck rows).

Runs right after a shop's pass, where that pass ran: on the server for
Douglas and makeup.lv, on the PC for Notino and 220.lv (the server's address
gets 403 there), whose results the PC uploads with its products.

The page parsers come from the 24.10 manual audit (180 listings), which
compared the database with saved product pages of all four shops.
"""
from __future__ import annotations

import html as H
import json
import random
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from loguru import logger
from sqlalchemy import select, text

from app.core.database import async_session_maker
from app.domain.models import PageCheck, PriceHistory, Product

DEALS_PER_SHOP = 30
RANDOM_PER_SHOP = 10
# Prices this close are the same price (rounding in the page markup).
SAME_PRICE = Decimal("0.011")
CHALLENGE = ("_cf_chl_opt", "Mazliet uzgaidiet", "<title>Just a moment", "neesat robots")
# A fresh browser context every this many pages: an open context keeps its
# connections, and thousands of them run Windows out of ports (28.10).
PAGES_PER_CONTEXT = 15


@dataclass
class PageResult:
    price: Optional[Decimal]
    in_stock: bool
    note: str = ""


def _vol(s: Optional[str]) -> Optional[str]:
    """"100 ml" / "100ml" / "100,0 ml" -> "100ml"."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(ml|g)\b", (s or "").lower())
    return f"{float(m.group(1).replace(',', '.')):g}{m.group(2)}" if m else None


def _want(volume: Optional[str]) -> Optional[str]:
    """The stored volume as the parsers label variants ("150ml refill")."""
    v = _vol(volume)
    if v and re.search(r"refill|uzpild", (volume or "").lower()):
        v += " refill"
    return v


def _dec(v) -> Optional[Decimal]:
    try:
        d = Decimal(str(v)).quantize(Decimal("0.01"))
    except Exception:
        return None
    return d if d > 0 else None


def parse_douglas(url: str, volume: Optional[str], page: str) -> Optional[PageResult]:
    """douglas.lv: the tealium data of every variant of the product."""
    page = H.unescape(page)
    m_item = re.search(r"item=(\d+)", url)
    item = m_item.group(1) if m_item else None
    ents = []
    for m in re.finditer(r'"primary_product_id":\["?(\d+)', page):
        seg = page[max(0, m.start() - 3000): m.start() + 3000]

        def g(k, seg=seg):
            found = re.search(r'"%s":\["?([^"\]]*)' % k, seg)
            return found.group(1) if found else None
        ents.append(dict(id=m.group(1), master=g("primary_product_master_id"), size=g("primary_product_size"),
                         price=g("primary_product_price"), avail=g("primary_product_availability_status")))
    if not ents:
        return None
    master = next((e["master"] for e in ents if e["id"] == item), None) if item else ents[0]["master"]
    variants = {_vol(e["size"]): e for e in ents if e["master"] == master and e["size"]}
    e = variants.get(_want(volume)) if volume else (next(iter(variants.values())) if len(variants) == 1 else None)
    if e is None and item:
        e = next((x for x in ents if x["id"] == item), None)
    if e is None:
        return None
    return PageResult(_dec(e["price"]), e["avail"] == "Available")


def parse_makeup(url: str, volume: Optional[str], page: str) -> Optional[PageResult]:
    """makeup.lv: the schema.org offer of each variant in the buy section."""
    variants: dict = {}
    for m in re.finditer(
        r'<div id="\d+" class="ProductBuySection__variant[^"]*" itemprop="offers"(.*?)</div>\s*'
        r'(?=<div id="\d+" class="ProductBuySection__variant|</div>)', page, re.S,
    ):
        seg = m.group(1)
        name = (re.search(r'itemprop="name" content="([^"]+)"', seg) or [None, ""])[1]
        price = re.search(r'itemprop="price" content="([^"]+)"', seg)
        av = re.search(r'itemprop="availability" href="([^"]+)"', seg)
        title = (re.search(r'ProductBuySection__title[^>]*>([^<]+)<', seg) or [None, name])[1]
        if price:
            variants[_vol(title) or _vol(name)] = PageResult(_dec(price.group(1)), bool(av and "InStock" in av.group(1)))
    if variants:
        if volume:
            return variants.get(_want(volume))
        return next(iter(variants.values())) if len(variants) == 1 else None
    one = re.search(
        r'ProductBuySection__container[^>]*itemprop="offers".{0,400}?itemprop="price" content="([^"]+)"'
        r'.{0,600}?itemprop="availability" href="([^"]+)"', page, re.S,
    )
    if one and _dec(one.group(1)):
        return PageResult(_dec(one.group(1)), "InStock" in one.group(2), "single offer")
    if "ProductBuySection__outOfStock" in page:
        return PageResult(None, False, "whole product out of stock")
    return None


def _text(x: str) -> str:
    x = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", x, flags=re.S)
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", x))).strip()


def parse_220(url: str, volume: Optional[str], page: str) -> Optional[PageResult]:
    """220.lv: the public price ("Parastā cena"), not the 220.lv PLUS member
    price, and the schema.org availability."""
    at = page.find("c-product__price-block")
    t = _text(page[max(0, at - 3000): at + 5000]) if at >= 0 else _text(page)
    reg = re.search(r"Parastā cena (\d[\d ]*) (\d\d) €", t)
    ld = re.search(r'"offers":\{"@type":"Offer","price":"([\d.]+)","priceCurrency":"EUR","availability":"([^"]+)"', page)
    price = _dec(reg.group(1).replace(" ", "") + "." + reg.group(2)) if reg else (_dec(ld.group(1)) if ld else None)
    if price is None:
        if "izpārdota" in t.lower():
            return PageResult(None, False, "sold out")
        return None
    in_stock = ("InStock" in ld.group(2)) if ld else ("Uz grozu" in t)
    return PageResult(price, in_stock)


def parse_notino(url: str, volume: Optional[str], page: str) -> Optional[PageResult]:
    """notino.lv: the page state (__APOLLO_STATE__) of every variant; in stock
    only when the shop says it can be bought."""
    m = re.search(r'<script[^>]*id="__APOLLO_STATE__"[^>]*>(.*?)</script>', page, re.S)
    if not m:
        return None
    try:
        state = json.loads(m.group(1))
    except ValueError:
        return None
    variants: dict = {}
    for k, o in state.items():
        if not k.startswith("CatalogVariant:") or not isinstance(o, dict):
            continue
        info = o.get("additionalInfo") or ""
        name = o.get("variantName") or ""
        label = _vol(info) or _vol(name)
        if label and re.search(r"uzpild|refill", (name + info).lower()):
            label += " refill"
        price = (o.get("price") or {}).get("value")
        if label and price is not None:
            in_stock = ((o.get("availability") or {}).get("state")) == "CanBeBought"
            variants.setdefault(label, PageResult(_dec(price), in_stock))
    if volume:
        return variants.get(_want(volume))
    return next(iter(variants.values())) if len(variants) == 1 else None


PARSERS = {"douglas.lv": parse_douglas, "makeup.lv": parse_makeup, "220.lv": parse_220, "notino.lv": parse_notino}


async def _fetch(ctx, url: str) -> Optional[str]:
    """The page as a visitor's browser renders it; None on an error or a
    challenge that did not clear by itself (never solved, never clicked)."""
    page = await ctx.new_page()
    try:
        await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,ico,woff,woff2}", lambda route: route.abort())
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        html = ""
        for _ in range(20):
            await page.wait_for_timeout(1000)
            html = await page.content()
            if not any(c in html for c in CHALLENGE):
                break
        await page.wait_for_timeout(1500)
        html = await page.content()
        if any(c in html for c in CHALLENGE) and len(html) < 60000:
            return None
        return html
    except Exception as e:
        logger.debug(f"page check: {url} not loaded: {e}")
        return None
    finally:
        try:
            await page.close()
        except Exception:
            pass


def _change_type(product: Product, price: Optional[Decimal], in_stock: bool) -> Optional[str]:
    """History change type for correcting `product` to the page (same order
    as the scraper: a stock change wins over a price change)."""
    change = None
    if price and product.last_price and product.last_price > 0 and abs(price - product.last_price) > SAME_PRICE:
        change = "price_down" if price < product.last_price else "price_up"
    if in_stock and not product.is_available and price:
        change = "back_in_stock"
    elif not in_stock and product.is_available:
        change = "out_of_stock"
    return change


async def check_products(shop: str, ids: list[tuple[int, str]]) -> list[PageCheck]:
    """Read each (product id, kind) on its product page; record a PageCheck,
    stamp the product, correct it to the page when they disagree."""
    parser = PARSERS.get(shop)
    if not parser or not ids:
        return []
    from app.core.browser import browser_manager

    out: list[PageCheck] = []
    ctx = None
    try:
        for n, (pid, kind) in enumerate(ids):
            if ctx is None or n % PAGES_PER_CONTEXT == 0:
                if ctx is not None:
                    await ctx.close()
                ctx = await browser_manager.get_context()
            async with async_session_maker() as session:
                product = await session.get(Product, pid)
                if product is None:
                    continue
                html = await _fetch(ctx, product.url)
                res = None
                note = "page not loaded" if html is None else ""
                if html is not None:
                    try:
                        res = parser(product.url, product.volume, html)
                    except Exception as e:
                        note = f"parse error {e!r}"[:120]
                    if res is None and not note:
                        note = "this size not found on the page"
                now = datetime.utcnow()
                check = PageCheck(product_id=pid, shop=shop, kind=kind, checked_at=now,
                                  db_price=product.last_price, db_in_stock=product.is_available)
                if res is not None:
                    check.page_price, check.page_in_stock = res.price, res.in_stock
                    same_price = res.price is None or (product.last_price is not None
                                                      and abs(res.price - product.last_price) <= SAME_PRICE)
                    check.ok = bool(same_price and res.in_stock == product.is_available)
                    note = res.note
                    change = _change_type(product, res.price, res.in_stock)
                    if change:
                        history_price = res.price or product.last_price
                        if history_price and history_price > 0:
                            session.add(PriceHistory(product_id=pid, price=history_price, in_stock=res.in_stock,
                                                     parsed_at=now, change_type=change))
                    if res.price and (product.last_price is None or abs(res.price - product.last_price) > SAME_PRICE):
                        product.old_price = product.last_price
                        product.last_price = res.price
                    product.is_available = res.in_stock
                    product.last_seen = now
                    product.page_checked_at = now
                    product.page_price = res.price if res.price else None
                    session.add(product)
                check.note = note[:255] or None
                session.add(check)
                await session.commit()
                out.append(check)
    except Exception as e:
        logger.warning(f"page check of {shop} stopped: {e}")
    finally:
        if ctx is not None:
            try:
                await ctx.close()
            except Exception:
                pass
    ok = sum(1 for c in out if c.ok)
    bad = sum(1 for c in out if c.ok is False)
    logger.info(f"page check {shop}: {len(out)} read, {ok} matched, {bad} corrected, "
                f"{len(out) - ok - bad} unreadable")
    return out


async def _random_sample(session, shop: str, skip: list[int]) -> list[int]:
    """RANDOM_PER_SHOP fresh in-stock listings of `shop`, not in `skip`."""
    pool = (await session.execute(text("""
        select id from product
        where search_term = :shop and is_available and last_price > 0
          and last_seen >= now() at time zone 'utc' - interval '30 hours'
          and not (id = any(:skip))
    """), {"shop": shop, "skip": skip or [0]})).scalars().all()
    return random.sample(list(pool), min(RANDOM_PER_SHOP, len(pool)))


async def deal_candidates(session, shop: str) -> list[Product]:
    """The listings of `shop` that would be on Today once confirmed."""
    from app.services import market

    deals = await market.deals(session, days=7, limit=DEALS_PER_SHOP,
                               stores=[shop.replace(".lv", "")], confirmed_only=False)
    ids = [d.product_id for d in deals]
    if not ids:
        return []
    rows = (await session.execute(select(Product).where(Product.id.in_(ids)))).scalars().all()
    order = {pid: n for n, pid in enumerate(ids)}
    return sorted(rows, key=lambda p: order[p.id])


async def check_after_pass(shop: str) -> list[PageCheck]:
    """After a pass over `shop` on the server: its best deal candidates (they
    are shown only when confirmed) and a few random in-stock listings (the audit)."""
    try:
        async with async_session_maker() as session:
            deal_ids = [p.id for p in await deal_candidates(session, shop)]
            sample = await _random_sample(session, shop, deal_ids)
    except Exception as e:
        logger.warning(f"page check of {shop} not started: {e}")
        return []
    return await check_products(shop, [(i, "deal") for i in deal_ids] + [(i, "random") for i in sample])


async def check_listed(shop: str, listings: list[dict]) -> list[PageCheck]:
    """On the PC: check the server's deal candidates (`listings` = [{url,
    volume}], from /admin/scrape/deal-candidates) plus a random sample. The
    PC's own database can hold other history, so its own candidates would
    not be the ones the site shows."""
    try:
        async with async_session_maker() as session:
            deal_ids: list[int] = []
            for item in listings:
                q = select(Product.id).where(Product.url == item.get("url"), Product.search_term == shop)
                vol = item.get("volume")
                q = q.where(Product.volume == vol) if vol else q.where(Product.volume.is_(None))
                pid = await session.scalar(q.order_by(Product.id).limit(1))
                if pid and pid not in deal_ids:
                    deal_ids.append(pid)
            sample = await _random_sample(session, shop, deal_ids)
    except Exception as e:
        logger.warning(f"page check of {shop} not started: {e}")
        return []
    if len(deal_ids) < len(listings):
        logger.info(f"page check {shop}: {len(listings) - len(deal_ids)} server candidates not in the local database")
    return await check_products(shop, [(i, "deal") for i in deal_ids] + [(i, "random") for i in sample])


async def checks_since(since: datetime, shop: Optional[str] = None) -> list[dict]:
    """Page checks made since `since`, with the listing's url and volume (the
    PC uploads them to the server, where product ids differ)."""
    async with async_session_maker() as session:
        q = (select(PageCheck, Product.url, Product.volume)
             .join(Product, Product.id == PageCheck.product_id)
             .where(PageCheck.checked_at >= since))
        if shop:
            q = q.where(PageCheck.shop == shop)
        rows = (await session.execute(q)).all()
    return [
        {
            "url": url, "volume": volume, "kind": c.kind, "checked_at": c.checked_at.isoformat(),
            "db_price": float(c.db_price) if c.db_price is not None else None,
            "page_price": float(c.page_price) if c.page_price is not None else None,
            "db_in_stock": c.db_in_stock, "page_in_stock": c.page_in_stock, "ok": c.ok, "note": c.note,
        }
        for c, url, volume in rows
    ]
