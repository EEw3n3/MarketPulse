"""Scrape review report — run the REAL scraper on catalog pages of one shop and
write an HTML table for manual verification against the site.

The scraper itself is not modified. This script wraps
`ScraperService._flush_candidates` (called once per catalog page) to record what
the scraper extracted, and records the shop's own data for the same pages:
  - makeup.lv: the category API pages (JSON);
  - douglas.lv: the catalog page HTML and the product pages (Tealium data) —
    product pages the scraper did not open itself are fetched by this script;
  - notino.lv: the catalog page HTML with its embedded listing state (every
    card's volumes, stock, price) and the product pages' Apollo state (price,
    stock and name of every variant). The scraper reads product pages through
    network traffic, so their HTML is taken from its own browser page just
    before it closes; pages it did not open are fetched by this script.
  - 220.lv: the catalog page HTML: every card's widget-data JSON (title, brand,
    stock) and its visible prices: the public price and the "220.lv PLUS"
    loyalty price (members only). One card = one volume (in the title).
Every card of a site page — including the ones the scraper dropped and the promo
tiles — appears in the report at its position, next to the shop's data for an
automatic cross-check. After the run it reads back what was stored in the
database (card type, comparison group, last price).

Modes:
    python scripts/scrape_review.py <site> --pages 3
        first N pages, in site order
    python scripts/scrape_review.py <site> --only 5,8
        the listed catalog pages only
    python scripts/scrape_review.py <site> --variations
        samples the catalog, picks pages holding every kind of card
        (gift sets, out of stock, multi-volume, refill, mini, ...), scrapes
        those pages and groups the examples by card kind

Sites: makeup, douglas, notino, 220 (notino: first pages only).

Output:
    reports/scrape_review_<domain>_<YYYY-MM-DD_HHMM>.html
    reports/scrape_variations_<domain>_<YYYY-MM-DD_HHMM>.html
"""
from __future__ import annotations

import argparse
import asyncio
import html
import json
import os
import random
import re
import sys
from datetime import datetime
from decimal import Decimal
from urllib.parse import urljoin, urlparse

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from loguru import logger
from parsel import Selector
from playwright.async_api import APIRequestContext, BrowserContext, Page
from sqlmodel import select

from app.core.browser import browser_manager
from app.core.client import stealth_client
from app.core.constants import PRODUCT_BLACKLIST
from app.core.database import async_session_maker
from app.domain.models import Product, ProductGroup, ScrapingRule
from app.main import get_hybrid_html
from app.services.ai_generator import ai_generator
from app.services.normalizer import (
    detect_card_type, is_non_perfume_set, is_non_perfume_title, perfume_normalizer, volume_qualifier,
)
from app.services.scraper import scraper_service

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPORTS_DIR = os.path.join(ROOT, "reports")
SUPPORTED_SITES = {"makeup", "douglas", "notino", "220"}
DEFAULT_STEP = {"makeup": 10, "douglas": 1, "220": 3}  # sample every N-th catalog page
MAKEUP_PAGE_SIZE = 36
NON_PERFUME_WORDS = list(PRODUCT_BLACKLIST)
# A miniature joins the full-size perfume's comparison group; a group named
# after the marker means the normalizer kept it in the name.
MINI_GROUP_RE = re.compile(r"\bmini\b|miniat", re.IGNORECASE)


class _StopReview(BaseException):
    """Stops the scraper after the requested pages. BaseException so the
    scraper's own `except Exception` blocks can't swallow it."""


class ReviewCapture:
    def __init__(self) -> None:
        self.flushed_pages: list[list[dict]] = []    # what the scraper saved, per page
        self.api_pages: list[tuple[str, dict]] = []   # makeup.lv category API pages
        self.run_api_pages = 0
        self.max_api_pages: int | None = None         # makeup: stop before fetching more
        self.run_flushes = 0
        self.max_flushes: int | None = None           # generic sites: stop after N saved pages
        self.catalog_pages: list[tuple[str, str]] = []  # (url, html) of catalog pages, in order
        self.fetched: dict[str, str] = {}             # every HTML page fetched, by URL
        self.review_fetched: set[str] = set()         # product pages opened by this script
        self.catalog_path: str | None = None          # notino: the category's URL path
        self.nav_listings: list = []                  # notino: navigation API answers (pages 2+)


# ── Hooks ────────────────────────────────────────────────────────────────────

def install_hooks(cap: ReviewCapture):
    orig_flush = scraper_service._flush_candidates
    orig_scrape_page = scraper_service.scrape_page
    orig_get_page = stealth_client.get_page
    orig_page_content = browser_manager.get_page_content
    orig_api_get = APIRequestContext.get
    orig_content = Page.content
    orig_close = Page.close
    orig_new_page = BrowserContext.new_page

    async def review_flush(session, candidates, rule, group_id, intent):
        cap.flushed_pages.append([dict(c) for c in candidates])
        logger.info(f"[REVIEW] saving page: {len(candidates)} entries")
        saved = await orig_flush(session, candidates, rule, group_id, intent)
        cap.run_flushes += 1
        if cap.max_flushes is not None and cap.run_flushes >= cap.max_flushes:
            raise _StopReview()
        return saved

    async def review_scrape_page(url, rule=None, browser_context=None, click_selector=None):
        resp = await orig_scrape_page(url, rule=rule, browser_context=browser_context, click_selector=click_selector)
        if resp and resp.get("html"):
            cap.catalog_pages.append((resp.get("url") or url, resp["html"]))
        return resp

    async def review_get_page(url, *args, **kwargs):
        page_html = await orig_get_page(url, *args, **kwargs)
        if page_html:
            cap.fetched[url] = page_html
        return page_html

    async def review_page_content(url, *args, **kwargs):
        resp = await orig_page_content(url, *args, **kwargs)
        if resp and resp.get("html"):
            cap.fetched[url] = resp["html"]
        return resp

    async def review_api_get(self, url, *args, **kwargs):
        is_catalog = "/shop/v1/categories/" in url
        if is_catalog and cap.max_api_pages is not None and cap.run_api_pages >= cap.max_api_pages:
            raise _StopReview()
        resp = await orig_api_get(self, url, *args, **kwargs)
        if is_catalog and resp.status == 200:
            cap.run_api_pages += 1
            try:
                cap.api_pages.append((url, json.loads(await resp.text())))
            except Exception as e:
                logger.warning(f"[REVIEW] could not record API page {url}: {e}")
        return resp

    # notino.lv: the scraper parses catalog pages from page.content() of its
    # own browser page, and reads product pages through network traffic.
    async def review_content(self, *args, **kwargs):
        page_html = await orig_content(self, *args, **kwargs)
        if page_html and is_notino_catalog(self.url, cap.catalog_path):
            record_catalog_page(cap, self.url, page_html)
        return page_html

    async def review_close(self, *args, **kwargs):
        try:
            if is_notino_product(self.url, cap.catalog_path):
                key = notino_product_key(self.url)
                if key not in cap.fetched:
                    cap.fetched[key] = await orig_content(self)
        except Exception:
            pass
        return await orig_close(self, *args, **kwargs)

    # notino.lv pages 2+ arrive through the navigation API, not as a new HTML page.
    async def review_new_page(self, *args, **kwargs):
        page = await orig_new_page(self, *args, **kwargs)

        async def keep_listing(resp):
            if "/api/navigation/navigation/" in resp.url:
                try:
                    cap.nav_listings.append(await resp.json())
                except Exception:
                    pass

        page.on("response", lambda resp: asyncio.ensure_future(keep_listing(resp)))
        return page

    # Review runs never answer a Cloudflare check (no clicks on its checkbox):
    # they only wait for a check that passes by itself.
    async def review_solve_cloudflare(page):
        for _ in range(15):
            if not await browser_manager._challenge_still_present(page):
                return True
            await asyncio.sleep(1)
        logger.warning("[REVIEW] Cloudflare check did not pass by itself; not answering it")
        return False

    scraper_service._flush_candidates = review_flush
    scraper_service.scrape_page = review_scrape_page
    stealth_client.get_page = review_get_page
    browser_manager.get_page_content = review_page_content
    browser_manager._solve_cloudflare = review_solve_cloudflare
    APIRequestContext.get = review_api_get
    Page.content = review_content
    Page.close = review_close
    BrowserContext.new_page = review_new_page

    def restore() -> None:
        for obj, name in ((scraper_service, "_flush_candidates"), (scraper_service, "scrape_page"),
                          (stealth_client, "get_page"), (browser_manager, "get_page_content"),
                          (browser_manager, "_solve_cloudflare")):
            obj.__dict__.pop(name, None)
        APIRequestContext.get = orig_api_get
        Page.content = orig_content
        Page.close = orig_close
        BrowserContext.new_page = orig_new_page

    return restore


def record_catalog_page(cap: ReviewCapture, url: str, page_html: str) -> None:
    """Keep one entry per catalog URL, in the order pages were first seen."""
    for i, (u, _) in enumerate(cap.catalog_pages):
        if u == url:
            cap.catalog_pages[i] = (url, page_html)
            return
    cap.catalog_pages.append((url, page_html))


# ── Running the scraper ──────────────────────────────────────────────────────

def find_target(site_key: str) -> dict:
    with open(os.path.join(ROOT, "configs", "categories.json"), "r", encoding="utf-8") as f:
        cats = json.load(f)
    for block in cats.values():
        for t in block.get("targets", []):
            if site_key.lower() in urlparse(t["url"]).netloc.lower():
                return t
    raise SystemExit(f"No target in configs/categories.json matches '{site_key}'")


def domain_of(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


async def reset_checkpoint(domain: str) -> None:
    """A partial run leaves ScrapingRule.last_page_url set, and the generic
    scraper resumes from it on the next run — clear it."""
    async with async_session_maker() as s:
        rule = (await s.execute(select(ScrapingRule).where(ScrapingRule.domain == domain))).scalar_one_or_none()
        if rule and (rule.last_page_url or rule.items_scraped_current_run):
            rule.last_page_url = None
            rule.items_scraped_current_run = 0
            s.add(rule)
            await s.commit()


async def clear_rule_checkpoint(session, rule) -> None:
    rule.last_page_url = None
    rule.items_scraped_current_run = 0
    session.add(rule)
    await session.commit()


async def get_rule(session, url: str):
    page_html = await get_hybrid_html(url)
    if not page_html:
        raise SystemExit(f"Could not load {url}")
    rule = await ai_generator.get_or_create_rule(session, url, page_html)
    if not rule:
        raise SystemExit(f"No scraping rule for {domain_of(url)}")
    return rule, page_html


async def run_first_pages(site: str, target: dict, cap: ReviewCapture, pages: int) -> None:
    url = target["url"]
    if site == "notino":
        cap.catalog_path = urlparse(url).path
    restore = install_hooks(cap)
    await stealth_client.init_session()
    try:
        async with async_session_maker() as session:
            rule, page_html = await get_rule(session, url)
            await clear_rule_checkpoint(session, rule)
            if site == "makeup":
                cap.run_api_pages, cap.max_api_pages = 0, pages
            else:
                cap.run_flushes, cap.max_flushes = 0, pages
            try:
                await scraper_service.scrape_catalog(
                    session, url, page_html, max_items=10**6, group_id=None, intent=None,
                    enable_price_filter=True, site_name_ui=target.get("site"),
                )
            except _StopReview:
                pass
        if site == "douglas":
            await fetch_missing_douglas_products(cap)
        elif site == "notino":
            await fetch_missing_notino_products(cap, pages)
        await reset_checkpoint(domain_of(url))
    finally:
        restore()
        await stealth_client.close()
        await browser_manager.stop()


async def run_makeup_pages(target: dict, cap: ReviewCapture, page_numbers: list[int]) -> None:
    """Scrape single makeup.lv pages (API offset per page) with the real scraper."""
    url = target["url"]
    restore = install_hooks(cap)
    await stealth_client.init_session()
    try:
        async with async_session_maker() as session:
            rule, _ = await get_rule(session, url)
            for page_no in page_numbers:
                cap.run_api_pages, cap.max_api_pages = 0, 1
                logger.info(f"[REVIEW] scraping page {page_no}")
                try:
                    await scraper_service._scrape_makeup_via_api(
                        session, rule, url, max_items=10**6, group_id=None, intent=None,
                        site_name_ui=target.get("site"), start_offset=(page_no - 1) * MAKEUP_PAGE_SIZE,
                    )
                except _StopReview:
                    pass
        await reset_checkpoint(domain_of(url))
    finally:
        restore()
        await stealth_client.close()
        await browser_manager.stop()


async def run_douglas_pages(target: dict, cap: ReviewCapture, page_numbers: list[int], page_url=None) -> None:
    """Scrape single catalog pages with the real (generic) scraper (douglas.lv, 220.lv)."""
    page_url = page_url or douglas_page_url
    url = target["url"]
    restore = install_hooks(cap)
    await stealth_client.init_session()
    try:
        async with async_session_maker() as session:
            rule, _ = await get_rule(session, url)
            for page_no in page_numbers:
                # The generic loop resumes from rule.last_page_url when it is set.
                await clear_rule_checkpoint(session, rule)
                cap.run_flushes, cap.max_flushes = 0, 1
                logger.info(f"[REVIEW] scraping page {page_no}")
                try:
                    await scraper_service.scrape_catalog(
                        session, page_url(url, page_no), None, max_items=10**6, group_id=None,
                        intent=None, enable_price_filter=True, site_name_ui=target.get("site"),
                    )
                except _StopReview:
                    pass
        if page_url is douglas_page_url:
            await fetch_missing_douglas_products(cap)
        await reset_checkpoint(domain_of(url))
    finally:
        restore()
        await stealth_client.close()
        await browser_manager.stop()


async def fetch_missing_douglas_products(cap: ReviewCapture) -> None:
    """Open product pages the scraper did not visit, for cards that have more
    than one volume, so the report knows every volume the shop sells."""
    todo = []
    for page_url, page_html in cap.catalog_pages:
        for card in Selector(text=page_html).css("div.product_element"):
            url = urljoin(page_url, card.css("a::attr(href)").get() or "")
            tealium = _json(card.css("a::attr(data-tealium-info)").get(""))
            price_text = " ".join(card.css("span.price span.now ::text").getall()).strip().lower()
            has_variants = _first(tealium, "primary_product_variants") == "yes" or price_text.startswith(("no ", "sākot"))
            if has_variants and url not in cap.fetched and url not in todo:
                todo.append(url)
    if todo:
        logger.info(f"[REVIEW] opening {len(todo)} product pages the scraper skipped")
    for url in todo:
        page_html = await stealth_client.get_page(url)
        if page_html:
            cap.fetched[url] = page_html
            cap.review_fetched.add(url)
        await asyncio.sleep(random.uniform(1.0, 2.0))


async def fetch_missing_notino_products(cap: ReviewCapture, pages: int) -> None:
    """Open product pages the scraper did not visit, for cards with more than
    one variant, so the report knows the price and stock of every volume."""
    todo = []
    for page_url, page_html in cap.catalog_pages[:pages]:
        for p in notino_page_listing(cap, notino_page_no(page_url), page_html).get("products") or []:
            url = urljoin(page_url, p.get("url") or "")
            if len(p.get("variants") or []) > 1 and url not in cap.fetched and url not in todo:
                todo.append(url)
    if todo:
        logger.info(f"[REVIEW] opening {len(todo)} product pages the scraper skipped")
    for url in todo:
        resp = await browser_manager.get_page_content(url, fast_mode=True, verified_domain=False)
        if resp and resp.get("html"):
            cap.fetched[url] = resp["html"]
            cap.review_fetched.add(url)
        await asyncio.sleep(random.uniform(1.0, 2.0))


# ── Sampling the catalog (no saving) ─────────────────────────────────────────

async def sample_makeup_catalog(category_url: str, step: int) -> tuple[list[dict], int]:
    """Read every `step`-th API page of the category."""
    cat_id = re.search(r"/categorys/(\d+)", category_url).group(1)
    ctx = await browser_manager.get_context()
    sampled: list[dict] = []
    try:
        page = await ctx.new_page()
        try:
            await page.goto(category_url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(3)
        finally:
            await page.close()
        total_pages, page_no = None, 1
        while total_pages is None or page_no <= total_pages:
            resp = await ctx.request.get(
                f"https://makeup.lv/shop/v1/categories/{cat_id}/products/?offset={(page_no - 1) * MAKEUP_PAGE_SIZE}",
                timeout=30000,
            )
            if resp.status == 200:
                data = json.loads(await resp.text())
                if total_pages is None:
                    total = int(data.get("totalCount") or data.get("total") or 0)
                    total_pages = max(1, -(-total // MAKEUP_PAGE_SIZE))
                for pos, p in enumerate(data.get("products") or [], start=1):
                    if p.get("type") == "product":
                        sampled.append({"page": page_no, "pos": pos, "kinds": classify_makeup(p)})
            else:
                logger.warning(f"[REVIEW] sample page {page_no}: HTTP {resp.status}")
                if total_pages is None:
                    break
            page_no += step
            await asyncio.sleep(0.3)
    finally:
        await ctx.close()
        await browser_manager.stop()
    return sampled, total_pages or 0


async def sample_douglas_catalog(category_url: str, step: int) -> tuple[list[dict], int]:
    """Read every `step`-th catalog page (HTML) and classify its cards."""
    sampled: list[dict] = []
    total_pages, page_no = None, 1
    await stealth_client.init_session()
    try:
        while total_pages is None or page_no <= total_pages:
            url = douglas_page_url(category_url, page_no)
            page_html = await stealth_client.get_page(url)
            if page_html:
                if total_pages is None:
                    numbers = [int(t) for t in Selector(text=page_html).css("a.page::text").getall() if t.strip().isdigit()]
                    total_pages = max(numbers or [1])
                for card in douglas_site_cards(url, page_html, page_no, {}, set()):
                    sampled.append({"page": page_no, "pos": card["pos"], "kinds": card["kinds"]})
            elif total_pages is None:
                break
            page_no += step
            await asyncio.sleep(random.uniform(0.8, 1.6))
    finally:
        await stealth_client.close()
        await browser_manager.stop()
    return sampled, total_pages or 0


async def sample_220_catalog(category_url: str, step: int) -> tuple[list[dict], int]:
    """Read every `step`-th catalog page (fresh browser context per page, as the
    scraper does) until a page has no cards or the shop sends back to page 1."""
    sampled: list[dict] = []
    page_no, last_page = 1, 0
    try:
        while page_no <= 200:
            url = s220_page_url(category_url, page_no)
            resp = await browser_manager.get_page_content(url, fast_mode=True, context=None, solve_cf=False)
            page_html = (resp or {}).get("html") or ""
            if page_no > 1 and resp and s220_page_no(resp.get("url") or "") != page_no:
                break
            cards = s220_site_cards(url, page_html, page_no)
            if not cards:
                break
            last_page = page_no
            for card in cards:
                sampled.append({"page": page_no, "pos": card["pos"], "kinds": card["kinds"]})
            page_no += step
            await asyncio.sleep(random.uniform(1.0, 2.0))
    finally:
        await browser_manager.stop()
    return sampled, last_page


# ── Card kinds ───────────────────────────────────────────────────────────────

VARIATION_KINDS = [
    # key, title, what correct handling looks like
    ("gift_set", "Подарочные наборы",
     "Тип «набор», без объёма и концентрации, в сравнение цен не попадает (нет группы)."),
    ("multi_volume", "Несколько объёмов на одной карточке",
     "Каждый объём — отдельная запись со своей ценой и наличием."),
    ("single_volume", "Один объём",
     "Одна запись с объёмом и ценой."),
    ("out_of_stock", "Нет в наличии",
     "Записано «нет в наличии»; цена не записывается как 0 € и не портит историю цен."),
    ("partial_na", "Часть объёмов нет в наличии",
     "Недоступные объёмы помечены «нет в наличии», доступные — «в наличии»."),
    ("refill", "Refill / Refillable",
     "Refill-вариант не склеивается с обычным флаконом того же объёма."),
    ("mini", "Миниатюры (mini)",
     "Сохраняется как отдельный маленький объём (до 30 ml) в той же группе сравнения, что и полноразмерный флакон."),
    ("discount", "Скидка (зачёркнутая цена)",
     "Сохраняется текущая цена. Старую цену со скидкой парсер пока не хранит."),
    ("grams", "Объём в граммах (твёрдые духи, стики)",
     "Объём в граммах распознаётся; не-парфюм (стик-дезодорант) отбрасывается."),
    ("non_perfume", "Не парфюм (дезодоранты, гели и т.п.)",
     "Должен отбрасываться: в базу духов не попадает."),
    ("tester", "Тестеры",
     "Тестер не должен склеиваться с обычным флаконом."),
]


def _common_kinds(title: str, sub: str, variants: list[dict], is_set: bool, extra_text: str = "") -> list[str]:
    """Kinds that are detected the same way for every shop."""
    both = f"{title} {sub} {extra_text}".lower()
    kinds = []
    if "refill" in both or any("refill" in v["value"].lower() for v in variants):
        kinds.append("refill")
    if re.search(r"\bmini\b|miniat", both):
        kinds.append("mini")
    if any(re.search(r"\d\s*g\b", v["value"]) for v in variants):
        kinds.append("grams")
    if is_set:
        if is_non_perfume_set(title, sub):
            kinds.append("non_perfume")
    elif (is_non_perfume_title(sub) or is_non_perfume_title(title)
          or any(w in sub.lower() or w in title.lower() for w in NON_PERFUME_WORDS)):
        kinds.append("non_perfume")
    if re.search(r"\btest(er|eris)\b", both):
        kinds.append("tester")
    return kinds


def _stock_kinds(in_stock: bool, variants: list[dict]) -> list[str]:
    # A variant's "available" is None when the shop's data doesn't say.
    known = [v["available"] for v in variants if v["available"] is not None]
    if not in_stock or (known and not any(known)):
        return ["out_of_stock"]
    if any(a is False for a in known):
        return ["partial_na"]
    return []


# ── makeup.lv adapter ────────────────────────────────────────────────────────

def makeup_page_url(category_url: str, page_no: int) -> str:
    cat_id = re.search(r"/categorys/(\d+)", category_url).group(1)
    return f"https://makeup.lv/categorys/{cat_id}/offset-{(page_no - 1) * MAKEUP_PAGE_SIZE}/"


def makeup_page_no(api_url: str) -> int:
    m = re.search(r"offset=(\d+)", api_url)
    return 1 + int(m.group(1)) // MAKEUP_PAGE_SIZE if m else 1


def makeup_variants(p: dict) -> list[dict]:
    not_avail = set()
    for x in p.get("notAvailableVariants") or []:
        not_avail.add(str(x.get("id")) if isinstance(x, dict) else str(x))
    out = []
    for vid, info in (((p.get("analytics") or {}).get("variantsData")) or {}).items():
        if isinstance(info, dict):
            out.append({
                "value": (info.get("value") or "").strip(),
                "price": _money(info.get("price")), "old": _money(info.get("price_old")),
                "available": bool(p.get("inStock")) and str(vid) not in not_avail,
            })
    return out


def classify_makeup(p: dict) -> list[str]:
    title = (p.get("title") or "").strip()
    sub = (p.get("subTitle") or "").strip()
    variants = makeup_variants(p)
    is_set = bool(p.get("isGift")) or detect_card_type(title, sub) == "gift_set"
    kinds = ["gift_set"] if is_set else (["multi_volume"] if len(variants) > 1 else (["single_volume"] if variants else []))
    kinds += _stock_kinds(bool(p.get("inStock")), variants)
    price_obj = p.get("price") or {}
    if any(v["old"] and v["price"] and v["old"] > v["price"] for v in variants) or price_obj.get("old"):
        kinds.append("discount")
    return kinds + _common_kinds(title, sub, variants, is_set)


def makeup_site_card(p: dict, pos: int, page_no: int, category_url: str) -> dict:
    page_url = makeup_page_url(category_url, page_no)
    if p.get("type") != "product":
        label = {"action": "рекламный баннер", "quote-slider": "блок с отзывами"}.get(p.get("type"), p.get("type"))
        return {"kind": "promo", "pos": pos, "page": page_no, "page_url": page_url, "label": label, "title": p.get("title") or ""}
    link = (p.get("link") or "").strip()
    media = p.get("media")
    if isinstance(media, list):
        media = media[0] if media and isinstance(media[0], dict) else {}
    media = media or {}
    sizes = media.get("sizes") or {}
    return {
        "kind": "product", "pos": pos, "page": page_no, "page_url": page_url,
        "url": f"https://makeup.lv{link}" if link.startswith("/") else link,
        "image": (sizes.get("sm") or {}).get("url") or (sizes.get("lg") or {}).get("url") or media.get("url"),
        "site_brand": ((p.get("brand") or {}).get("title") or "").strip(),
        "site_title": (p.get("title") or "").strip(), "site_sub": (p.get("subTitle") or "").strip(),
        "site_vars": makeup_variants(p), "kinds": classify_makeup(p), "in_stock": bool(p.get("inStock")),
        "badges": [str(p["badge"])] if p.get("badge") else [], "card_text": "", "variants_note": "",
    }


# ── douglas.lv adapter ───────────────────────────────────────────────────────

def douglas_page_url(category_url: str, page_no: int) -> str:
    return category_url if page_no <= 1 else f"{category_url}?&page={page_no}"


def douglas_page_no(url: str) -> int:
    m = re.search(r"[?&]page=(\d+)", url)
    return int(m.group(1)) if m else 1


def _douglas_available(status) -> bool:
    s = str(status or "").lower()
    return bool(s) and not any(x in s for x in ("out of stock", "soon", "nav pieejams", "drīz", "not available", "unavailable"))


def douglas_product_variants(page_html: str) -> list[dict]:
    """Every volume listed in the product page's Tealium blocks."""
    out, seen = [], set()
    for raw in Selector(text=page_html).css("[data-tealium-info-view]::attr(data-tealium-info-view)").getall():
        d = _json(raw)
        if not isinstance(d, dict):
            continue
        names = d.get("primary_product_variant_name") or []
        prices = d.get("primary_product_price") or []
        regulars = d.get("primary_product_price_regular") or []
        statuses = d.get("primary_product_availability_status") or []
        for i in range(max(len(names), len(prices))):
            name = html.unescape(str(names[i] or "")).strip() if i < len(names) else ""
            key = name or f"#{i}"
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "value": name,
                "price": _money(prices[i]) if i < len(prices) else None,
                "old": _money(regulars[i]) if i < len(regulars) else None,
                "available": _douglas_available(statuses[i] if i < len(statuses) else None),
            })
    return out


def douglas_site_cards(page_url: str, page_html: str, page_no: int,
                       product_html_by_url: dict[str, str], review_fetched: set[str]) -> list[dict]:
    cards = []
    for pos, card in enumerate(Selector(text=page_html).css("div.product_element"), start=1):
        url = urljoin(page_url, card.css("a::attr(href)").get() or "")
        brand = " ".join(t.strip() for t in card.css("span.brand_caps ::text").getall() if t.strip())
        name = " ".join(t.strip() for t in card.css("span.name ::text").getall() if t.strip())
        if brand and name.upper().startswith(brand.upper()):
            name = name[len(brand):].strip()
        type_text = " ".join(t.strip() for t in card.css("span.type ::text").getall() if t.strip())
        price_text = " ".join(t.strip() for t in card.css("span.price span.now ::text").getall() if t.strip())
        volume_text = " ".join(t.strip() for t in card.css("span.volume ::text").getall() if t.strip())
        badges = [t.strip() for t in card.css(".bubbles ::text").getall() if t.strip()]
        image = card.css("img.product-photo::attr(src)").get() or card.css("img.product-photo::attr(data-src)").get()
        tealium = _json(card.css("a::attr(data-tealium-info)").get(""))
        card_var = None
        if _first(tealium, "primary_product_variant_name") or _first(tealium, "primary_product_price"):
            card_var = {
                "value": html.unescape(str(_first(tealium, "primary_product_variant_name") or "")).strip(),
                "price": _money(_first(tealium, "primary_product_price")),
                "old": _money(_first(tealium, "primary_product_price_regular")),
                "available": _douglas_available(_first(tealium, "primary_product_availability_status")),
            }
        product_html = product_html_by_url.get(url)
        if product_html and douglas_product_variants(product_html):
            site_vars = douglas_product_variants(product_html)
            note = "объёмы: страница товара (" + ("открыл отчёт" if url in review_fetched else "открыл парсер") + ")"
        else:
            site_vars = [card_var] if card_var else []
            note = "объём: карточка каталога"
        in_stock = bool(re.search(r"\d", price_text)) and (not site_vars or any(v["available"] for v in site_vars))
        classification = str(_first(tealium, "primary_product_classification") or "")
        is_set = detect_card_type(name, type_text, classification) == "gift_set"
        multi = len(site_vars) > 1 or price_text.lower().startswith(("no ", "sākot"))
        kinds = ["gift_set"] if is_set else (["multi_volume"] if multi else (["single_volume"] if site_vars else []))
        kinds += _stock_kinds(in_stock, site_vars)
        if _first(tealium, "primary_product_onsale") == "1" or any(v["old"] and v["price"] and v["old"] > v["price"] for v in site_vars):
            kinds.append("discount")
        kinds += _common_kinds(name, type_text, site_vars, is_set, classification)
        cards.append({
            "kind": "product", "pos": pos, "page": page_no, "page_url": page_url, "url": url,
            "image": urljoin(page_url, image) if image else None,
            "site_brand": brand, "site_title": name, "site_sub": type_text,
            "site_vars": site_vars, "kinds": kinds, "in_stock": in_stock, "badges": badges,
            "card_text": " · ".join(x for x in (price_text, volume_text) if x), "variants_note": note,
        })
    return cards


# ── 220.lv adapter ───────────────────────────────────────────────────────────

S220_PLUS = "220.lv PLUS"


def s220_page_url(category_url: str, page_no: int) -> str:
    return category_url if page_no <= 1 else f"{category_url}?page={page_no}"


def s220_page_no(url: str) -> int:
    m = re.search(r"[?&]page=(\d+)", url or "")
    return int(m.group(1)) if m else 1


def _price_label(label: str | None) -> Decimal | None:
    """aria-label "44,24 €" → Decimal("44.24")."""
    m = re.search(r"\d+(?:[.,]\d+)?", re.sub(r"\s+", "", label or ""))
    return _money(m.group(0).replace(",", ".")) if m else None


def s220_site_cards(page_url: str, page_html: str, page_no: int) -> list[dict]:
    """The prices visible on the card (not the widget JSON the scraper reads)
    are the site side of the price check."""
    cards = []
    for pos, card in enumerate(Selector(text=page_html).css("div.c-product-card"), start=1):
        data = _json(card.attrib.get("widget-data"))
        dl = data.get("dataLayerItem") or {}
        title = html.unescape(data.get("title") or " ".join(card.css(".c-product-card__title ::text").getall())).strip()
        url = data.get("url") or urljoin(page_url, card.css("a::attr(href)").get() or "")
        prices = card.css(".c-product-card__prices")
        loyalty = _price_label(prices.css(".h-price--loyalty::attr(aria-label)").get())
        public = _price_label(prices.css(".c-price:not(.h-price--loyalty):not(.c-price--leasing)::attr(aria-label)").get())
        in_stock = str(dl.get("item_status") or "active") == "active" and bool(public or loyalty)
        is_set = detect_card_type(title) == "gift_set"
        volume = re.search(r"\d+(?:[.,]\d+)?\s*(?:ml|l|g)\b", title, re.IGNORECASE)
        site_vars = [] if is_set else [{
            "value": " ".join(x for x in (volume.group(0), volume_qualifier(title)) if x) if volume else "",
            "price": public, "old": None,
            "available": in_stock, "promo_price": loyalty, "promo_code": S220_PLUS if loyalty else None,
        }]
        kinds = ["gift_set"] if is_set else ["single_volume"]
        kinds += _stock_kinds(in_stock, site_vars)
        kinds += _common_kinds(title, "", site_vars, is_set)
        badges = [f"цена {S220_PLUS}: {loyalty} €"] if loyalty else []
        card_text = " · ".join(x for x in (
            f"{public} €" if public else "", f"{S220_PLUS} {loyalty} €" if loyalty else "") if x)
        cards.append({
            "kind": "product", "pos": pos, "page": page_no, "page_url": page_url, "url": url,
            "image": re.sub(r"_(?:xsmall|small|medium|large|big)\.(jpe?g|png|webp)$", r"_reference.\1",
                            card.css("img.main-image::attr(src)").get() or data.get("photoUrl") or ""),
            "site_brand": dl.get("item_brand") or "", "site_title": title,
            "site_sub": "", "site_vars": site_vars, "kinds": kinds, "in_stock": in_stock, "badges": badges,
            "card_text": card_text, "variants_note": "объём: из названия карточки",
            "sets_not_stored": True,
        })
    return cards


# ── notino.lv adapter ────────────────────────────────────────────────────────

def is_notino_catalog(url: str, catalog_path: str | None) -> bool:
    return bool(catalog_path) and "notino.lv" in (url or "") and urlparse(url).path == catalog_path


def is_notino_product(url: str, catalog_path: str | None) -> bool:
    parts = [p for p in urlparse(url or "").path.split("/") if p]
    return bool(catalog_path) and "notino.lv" in (url or "") and len(parts) >= 2


def notino_product_key(url: str) -> str:
    """Product page URL without the selected variant ("…/p-16386742/")."""
    return re.sub(r"p-\d+/?$", "", url.split("?")[0].split("#")[0])


def notino_page_no(url: str) -> int:
    m = re.search(r"[?&]f=(\d+)-", url)
    return int(m.group(1)) if m else 1


def _find_listing(o):
    if isinstance(o, dict):
        prods = o.get("products")
        if isinstance(prods, list) and prods and isinstance(prods[0], dict) and "productCode" in prods[0]:
            return o
        for v in o.values():
            found = _find_listing(v)
            if found:
                return found
    elif isinstance(o, list):
        for v in o:
            found = _find_listing(v)
            if found:
                return found
    return None


def notino_listing(page_html: str) -> dict:
    """The catalog's own data for the page's cards (embedded React state)."""
    for raw in Selector(text=page_html).css("script[type='application/json']::text").getall():
        if '"productCode"' in raw and '"variants"' in raw:
            found = _find_listing(_json(raw))
            if found:
                return found
    return {}


def notino_page_listing(cap: "ReviewCapture", page_no: int, page_html: str) -> dict:
    """The shop's own list for a catalog page: page 1 from its HTML, pages 2+
    from the navigation API answer (their HTML still embeds page 1's list)."""
    if page_no > 1 and cap.nav_listings:
        on_page = {h for h in Selector(text=page_html).css("[data-testid='product-container'] a::attr(href)").getall()}
        best, best_overlap = None, 0
        for payload in cap.nav_listings:
            found = _find_listing(payload)
            overlap = len(on_page & {p.get("url") for p in (found or {}).get("products") or []})
            if overlap > best_overlap:
                best, best_overlap = found, overlap
        if best:
            return best
    return notino_listing(page_html)


def _notino_in_stock(stock) -> bool:
    s = str(stock or "").lower()
    return bool(s) and not any(x in s for x in ("outofstock", "notavailable", "none", "soldout"))


def notino_product_variants(page_html: str, product_path: str) -> list[dict]:
    """Every variant in the product page's Apollo state: volume (+ pack label,
    Notino names a refill "…vīriešiem refill"), price, stock."""
    state = _json(Selector(text=page_html).css("script#__APOLLO_STATE__::text").get(""))
    out = []
    for key, v in (state or {}).items():
        if not key.startswith("CatalogVariant:") or not isinstance(v, dict):
            continue
        if product_path and not str(v.get("url") or "").startswith(product_path):
            continue
        volume = (v.get("additionalInfo") or "").strip()  # "100 ml" or "150 ml Uzpilde"
        qualifier = volume_qualifier(f'{volume} {v.get("variantName") or ""} {v.get("variantType") or ""}')
        voucher = (v.get("attributes") or {}).get("VoucherDiscount") or {}
        out.append({
            "value": f"{volume} {qualifier}" if qualifier and not volume_qualifier(volume) else volume,
            "price": _money((v.get("price") or {}).get("value")),
            "old": _money((v.get("originalPrice") or {}).get("value")),
            "available": (v.get("availability") or {}).get("state") == "CanBeBought",
            "name": v.get("variantName") or "",
            "promo_price": _money(voucher.get("discountedPrice")),
            "promo_code": voucher.get("code") if voucher.get("discountedPrice") else None,
        })
    return out


def notino_site_cards(page_url: str, page_html: str, page_no: int,
                      product_html_by_url: dict[str, str], review_fetched: set[str],
                      listing_data: dict | None = None) -> list[dict]:
    """listing_data: the navigation API's list for pages 2+ (their HTML still
    embeds page 1's list)."""
    source = listing_data or notino_listing(page_html)
    listing = {urljoin(page_url, p.get("url") or ""): p for p in source.get("products") or []}
    cards = []
    for pos, card in enumerate(Selector(text=page_html).css("[data-testid='product-container']"), start=1):
        if (card.attrib.get("data-recommendation") or "").startswith("promo-banner"):  # promo-banner, promo-banner-2
            cards.append({"kind": "promo", "pos": pos, "page": page_no, "page_url": page_url,
                          "label": "рекламный баннер", "title": ""})
            continue
        url = urljoin(page_url, card.css("a::attr(href)").get() or "")
        p = listing.get(url, {})
        brand = " ".join(t.strip() for t in card.css("[data-testid='product-card-brand'] ::text, [data-testid='product-tile-brand'] ::text").getall() if t.strip())
        name = " ".join(t.strip() for t in card.css("[data-testid='product-card-name'] ::text, [data-testid='product-tile-name'] ::text").getall() if t.strip())
        type_text = " ".join(t.strip() for t in card.css("[data-testid='product-card-variant-name'] ::text, [data-testid='product-tile-variant-name'] ::text").getall() if t.strip())
        price_text = " ".join(t.strip() for t in card.css("[data-testid='product-price'] ::text").getall() if t.strip())
        badges = [t.strip() for t in card.css("[data-testid='default-product-label'] ::text").getall() if t.strip()]
        if p.get("isSponsored"):
            badges.append("Sponsorēts")
        image = card.css("img::attr(src)").get()
        price_info = p.get("priceInformation") or {}
        promo = p.get("promotionData") or {}
        variants = p.get("variants") or []
        product_html = product_html_by_url.get(url)
        product_vars = notino_product_variants(product_html, urlparse(url).path) if product_html else []
        if product_vars:
            site_vars = product_vars
            note = "объёмы: страница товара (" + ("открыл отчёт" if url in review_fetched else "открыл парсер") + ")"
        elif len(variants) <= 1:
            volume = (variants[0].get("additionalInfo") if variants else "") or ""
            site_vars = [{"value": volume, "price": _money(price_info.get("price")),
                          "old": _money(price_info.get("originalPrice")),
                          "available": _notino_in_stock(p.get("stockAvailability"))}] if p else []
            note = "объём: данные каталога"
        else:
            # Several variants but no product page: the card's "sākot ar" price is
            # the cheapest variant's, so per-variant price and stock are unknown.
            site_vars = [{"value": v.get("additionalInfo") or "", "price": None, "old": None, "available": None}
                         for v in variants]
            note = "объёмы: данные каталога (страница товара не открылась)"
        in_stock = any(v["available"] for v in site_vars) if product_vars else _notino_in_stock(p.get("stockAvailability"))
        is_set = detect_card_type(name, type_text) == "gift_set"
        multi = len(site_vars) > 1 or "sākot" in price_text.lower()
        kinds = ["gift_set"] if is_set else (["multi_volume"] if multi else (["single_volume"] if site_vars else []))
        kinds += _stock_kinds(in_stock, site_vars)
        if (p.get("discountReason") == "OnSale" or promo.get("voucherCode") or price_info.get("originalPrice")
                or any(v["old"] and v["price"] and v["old"] > v["price"] for v in site_vars)):
            kinds.append("discount")
        kinds += _common_kinds(name, type_text, site_vars, is_set, str(p.get("primaryType") or ""))
        if promo.get("voucherCode"):
            badges.append(f"промокод «{promo['voucherCode']}»")
        cards.append({
            "kind": "product", "pos": pos, "page": page_no, "page_url": page_url, "url": url,
            "image": image, "site_brand": brand, "site_title": name, "site_sub": type_text,
            "site_vars": site_vars, "kinds": kinds, "in_stock": in_stock, "badges": badges,
            "card_text": price_text + (" €" if price_text and "€" not in price_text else ""), "variants_note": note,
        })
    return cards


# ── Evaluation (same for every shop) ─────────────────────────────────────────

def _json(raw):
    try:
        return json.loads(raw) if raw else {}
    except Exception:
        try:
            return json.loads(html.unescape(raw))
        except Exception:
            return {}


def _first(d: dict, key: str):
    v = (d or {}).get(key)
    return v[0] if isinstance(v, list) and v else (v if not isinstance(v, list) else None)


def _vol_key(text: str | None) -> str | None:
    """"100 ml" → "100ml"; a pack variant keeps its label: "100 ml Refill" → "100ml refill"."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(ml|l|g|oz)\b", text or "", re.IGNORECASE)
    if not m:
        return None
    qualifier = volume_qualifier(text)
    return f"{m.group(1).replace(',', '.')}{m.group(2).lower()}" + (f" {qualifier}" if qualifier else "")


def _money(v) -> Decimal | None:
    try:
        return Decimal(str(v)).quantize(Decimal("0.01")) if v not in (None, "") else None
    except Exception:
        return None


def _plural_volumes(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} объём"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} объёма"
    return f"{n} объёмов"


def evaluate_card(card: dict, cand_by_url: dict, db_by_url: dict) -> dict:
    if card["kind"] != "product":
        return card
    title, sub, kinds = card["site_title"], card["site_sub"], card["kinds"]
    site_vars = card["site_vars"]
    cands = cand_by_url.get(card["url"], [])
    db_rows = db_by_url.get(card["url"], [])
    is_set = "gift_set" in kinds

    drop_reason = None
    if not cands:
        bl = [b for b in PRODUCT_BLACKLIST if b in title.lower()]
        sub_bl = [b for b in PRODUCT_BLACKLIST if b in sub.lower()]
        if is_set and card.get("sets_not_stored"):
            drop_reason = "подарочный набор: наборы из этого магазина не сохраняются"
        elif is_set and is_non_perfume_set(title, sub):
            drop_reason = f"набор без парфюма: «{sub}»"
        elif bl:
            drop_reason = f"чёрный список: «{bl[0]}»"
        elif is_non_perfume_title(title):
            drop_reason = "фильтр «не парфюм» по названию"
        elif not is_set and (sub_bl or is_non_perfume_title(sub)):
            drop_reason = f"не парфюм по подзаголовку: «{sub}»"
        else:
            drop_reason = "не сохранён (причина не определена)"
    # Non-perfumes are supposed to be dropped: that outcome is correct.
    expected_drop = "non_perfume" in kinds or (is_set and bool(card.get("sets_not_stored")))

    tags = []
    if is_set:
        tags.append(("gift", "подарочный набор"))
    tags.append(("vol", _plural_volumes(len(site_vars)) if site_vars else "без вариантов"))
    for k, label, cls in (("refill", "refill-вариант", "info"), ("mini", "mini", "info"),
                          ("grams", "граммы", "info"), ("tester", "тестер", "warn"),
                          ("non_perfume", "не парфюм", "warn"), ("out_of_stock", "нет в наличии", "warn"),
                          ("partial_na", "часть объёмов нет в наличии", "warn"), ("discount", "скидка", "info")):
        if k in kinds:
            tags.append((cls, label))
    tags += [("badge", b) for b in card.get("badges") or []]

    issues = []
    if "non_perfume" in kinds and cands:
        if is_set:
            issues.append(f"в наборе нет парфюма («{sub}»), но он сохранён")
        else:
            issues.append(f"на сайте это «{sub or title}», а парсер сохранил его как духи")
    if cands and is_set and card.get("sets_not_stored"):
        issues.append("набор сохранён, хотя наборы из этого магазина не сохраняются")
    if cands and is_set:
        if any(c.get("card_type") != "gift_set" for c in cands):
            issues.append("набор сохранён не как набор")
        if any(r["group"] for r in db_rows):
            issues.append("набор попал в группу сравнения цен")
    if cands and not is_set:
        cand_by_vol: dict[str, list[dict]] = {}
        for c in cands:
            cand_by_vol.setdefault(_vol_key(c.get("volume")) or "?", []).append(c)
        seen: dict[str, str] = {}
        for v in site_vars:
            k = _vol_key(v["value"]) or "?"
            if k in seen:
                issues.append(f"на сайте два варианта с объёмом {k} («{seen[k]}» и «{v['value']}») — в базе склеятся в один")
            seen[k] = v["value"]
            got = cand_by_vol.get(k)
            if not got:
                state = " (нет в наличии)" if v["available"] is False else ""
                issues.append(f"объём «{v['value']}»{state} есть на сайте, парсер его не сохранил")
                continue
            c = got[-1]
            cp = _money(c["price"]) if c["price"] else None
            if cp is None:
                if v["available"] and v["price"]:
                    issues.append(f"{v['value']}: на сайте цена {v['price']} €, парсер цену не взял")
            elif v["price"] is not None and cp != v["price"]:
                issues.append(f"{v['value']}: цена на сайте {v['price']} €, у парсера {cp} €")
            site_promo, cand_promo = v.get("promo_price"), _money(c.get("promo_price"))
            if site_promo and cand_promo != site_promo:
                issues.append(f"{v['value']}: на сайте цена с кодом «{v.get('promo_code')}» {site_promo} €, "
                              + (f"у парсера {cand_promo} €" if cand_promo else "парсер её не сохранил"))
            elif cand_promo and "promo_price" in v and not site_promo:
                issues.append(f"{v['value']}: парсер сохранил цену с кодом {cand_promo} €, а на сайте кода нет")
            if v["available"] is False and c.get("is_available"):
                issues.append(f"{v['value']}: на сайте нет в наличии, парсер пишет «в наличии»")
            if v["available"] and not c.get("is_available") and card["in_stock"]:
                issues.append(f"{v['value']}: на сайте в наличии, парсер пишет «нет в наличии»")
        for k in cand_by_vol:
            if site_vars and k not in seen:
                issues.append("парсер сохранил запись без объёма" if k == "?" else
                              f"парсер сохранил объём {k}, которого нет в вариантах сайта")
        if not site_vars and card["in_stock"] and any(not c.get("volume") for c in cands):
            issues.append("объём не определён (у карточки на сайте нет вариантов объёма)")
        groups = sorted({r["group"] for r in db_rows if r["group"]})
        if len(groups) > 1:
            issues.append("объёмы одной карточки попали в разные группы сравнения: " + "; ".join(groups))
        mini_groups = [g for g in groups if MINI_GROUP_RE.search(g)]
        if "mini" in kinds and mini_groups and any(
                perfume_normalizer.is_mini_volume(_vol_key(c.get("volume"))) for c in cands):
            issues.append(f"миниатюра попала в отдельную группу «{'; '.join(mini_groups)}», а не к полноразмерному флакону")
        if sub and not any(c.get("concentration") for c in cands) and "non_perfume" not in kinds:
            issues.append(f"концентрация не распознана (на сайте: «{sub}»)")
    if cands and not card["in_stock"] and any(c.get("is_available") for c in cands):
        issues.append("на сайте нет в наличии, парсер пишет «в наличии»")
    site_prices = {_vol_key(v["value"]): v["price"] for v in site_vars if v["price"] and v["available"]}
    for r in db_rows:
        if r["last_price"] is not None and r["last_price"] == 0 and site_prices.get(_vol_key(r["volume"])):
            issues.append(f"{r['volume'] or 'без объёма'}: в базе цена 0 €, хотя магазин знает цену")

    if not cands:
        status = "ok" if expected_drop else "dropped"
    else:
        status = "flagged" if issues else "ok"
    return {**card, "cands": cands, "db_rows": db_rows, "drop_reason": drop_reason, "tags": tags,
            "issues": issues, "status": status, "expected_drop": expected_drop}


async def load_db_rows(urls: list[str]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    if not urls:
        return out
    async with async_session_maker() as s:
        res = await s.execute(
            select(Product, ProductGroup.name)
            .join(ProductGroup, Product.group_id == ProductGroup.id, isouter=True)
            .where(Product.url.in_(urls))
        )
        for prod, group_name in res.all():
            out.setdefault(prod.url, []).append({
                "card_type": prod.card_type, "group": group_name, "volume": prod.volume,
                "last_price": prod.last_price, "is_available": prod.is_available,
            })
    return out


def candidates_by_url(cap: ReviewCapture) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for page in cap.flushed_pages:
        for c in page:
            out.setdefault(c["url"], []).append(c)
    return out


def site_pages(site: str, cap: ReviewCapture, category_url: str) -> list[dict]:
    """The scraped pages as [{page, page_url, cards}] in the shop's own order."""
    pages = []
    if site == "makeup":
        for api_url, data in cap.api_pages:
            page_no = makeup_page_no(api_url)
            cards = [makeup_site_card(p, pos, page_no, category_url) for pos, p in enumerate(data.get("products") or [], start=1)]
            pages.append({"page": page_no, "page_url": makeup_page_url(category_url, page_no), "cards": cards})
    elif site == "220":
        for page_url, page_html in cap.catalog_pages:
            page_no = s220_page_no(page_url)
            pages.append({"page": page_no, "page_url": page_url, "cards": s220_site_cards(page_url, page_html, page_no)})
    elif site == "notino":
        for page_url, page_html in cap.catalog_pages:
            page_no = notino_page_no(page_url)
            cards = notino_site_cards(page_url, page_html, page_no, cap.fetched, cap.review_fetched,
                                      notino_page_listing(cap, page_no, page_html))
            pages.append({"page": page_no, "page_url": page_url, "cards": cards})
    else:
        for page_url, page_html in cap.catalog_pages:
            page_no = douglas_page_no(page_url)
            cards = douglas_site_cards(page_url, page_html, page_no, cap.fetched, cap.review_fetched)
            pages.append({"page": page_no, "page_url": page_url, "cards": cards})
    return pages


async def evaluate_pages(pages: list[dict], cap: ReviewCapture) -> list[dict]:
    cand = candidates_by_url(cap)
    urls = [c["url"] for pg in pages for c in pg["cards"] if c["kind"] == "product"]
    db = await load_db_rows(urls)
    return [{**pg, "rows": [evaluate_card(c, cand, db) for c in pg["cards"]]} for pg in pages]


# ── HTML ─────────────────────────────────────────────────────────────────────

def e(v) -> str:
    return html.escape("" if v is None else str(v))


CSS = """
:root { --bg:#f6f7f9; --card:#fff; --text:#1c2230; --muted:#6b7385; --line:#e3e6ec; --accent:#0f766e;
  --ok:#15803d; --warn:#b45309; --warnbg:#fff4e0; --bad:#b91c1c; --badbg:#fdecec; --info:#1d4ed8; --infobg:#e8efff; }
@media (prefers-color-scheme: dark) { :root { --bg:#12151b; --card:#1a1f28; --text:#e6e9ef; --muted:#9aa3b5; --line:#2b323e; --accent:#2dd4bf;
  --ok:#4ade80; --warn:#fbbf24; --warnbg:#3a2c10; --bad:#f87171; --badbg:#3a1717; --info:#93b4ff; --infobg:#1b2745; } }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text); font:14px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; }
header { position:sticky; top:0; z-index:5; background:var(--card); border-bottom:1px solid var(--line); padding:14px 20px; }
h1 { font-size:20px; margin:0 0 4px; } h2 { font-size:17px; margin:0; }
.muted { color:var(--muted); }
.stats { display:flex; flex-wrap:wrap; gap:8px; margin:10px 0; }
.stat { background:var(--bg); border:1px solid var(--line); border-radius:8px; padding:6px 10px; }
.stat b { font-size:16px; }
.controls { display:flex; flex-wrap:wrap; gap:14px; align-items:center; }
.controls input[type=search] { padding:7px 10px; border:1px solid var(--line); border-radius:8px; background:var(--bg); color:var(--text); min-width:260px; }
main { padding:16px 20px 60px; }
.note { background:var(--infobg); border-radius:8px; padding:10px 14px; margin-bottom:16px; }
.page { background:var(--card); border:1px solid var(--line); border-radius:10px; margin-bottom:22px; overflow:hidden; }
.page-head { display:flex; gap:12px; align-items:center; padding:12px 14px; border-bottom:1px solid var(--line); flex-wrap:wrap; }
.expect { padding:8px 14px; border-bottom:1px solid var(--line); background:var(--bg); }
.btn { margin-left:auto; background:var(--accent); color:#fff; text-decoration:none; padding:7px 12px; border-radius:8px; font-weight:600; }
table { width:100%; border-collapse:collapse; }
th { text-align:left; font-size:12px; text-transform:uppercase; letter-spacing:.03em; color:var(--muted); padding:8px 10px; border-bottom:1px solid var(--line); background:var(--card); }
td { padding:9px 10px; border-bottom:1px solid var(--line); vertical-align:top; }
.c-pos { width:70px; font-weight:700; color:var(--muted); }
.c-img { width:110px; }
.c-img img { width:96px; height:96px; object-fit:contain; background:#fff; border-radius:6px; }
.brand { font-weight:700; }
.link { color:var(--accent); font-size:13px; }
.vol { display:grid; grid-template-columns:90px 80px auto; gap:2px 6px; white-space:nowrap; margin-bottom:4px; }
.vol-note { grid-column:1 / -1; white-space:normal; font-size:13px; }
.yes { color:var(--ok); } .no { color:var(--bad); } .ok { color:var(--ok); }
.tag { display:inline-block; font-size:12px; border-radius:20px; padding:1px 8px; margin:0 4px 4px 0; border:1px solid var(--line); }
.t-gift { background:var(--badbg); color:var(--bad); } .t-warn { background:var(--warnbg); color:var(--warn); }
.t-info { background:var(--infobg); color:var(--info); } .t-vol { background:var(--bg); } .t-badge { color:var(--muted); }
tr.promo td { background:var(--bg); font-size:13px; }
tr.st-flagged td { background:var(--warnbg); }
tr.st-dropped td { background:var(--badbg); }
.warn-title { color:var(--warn); font-weight:700; }
.dropped-label { color:var(--bad); font-weight:700; }
ul { margin:4px 0 0; padding-left:18px; }
.summary td, .summary th { padding:6px 10px; }
@media (max-width: 900px) { table, thead, tbody, tr, td, th { display:block; } thead { display:none; } td { border:none; padding:4px 10px; } tr { border-bottom:1px solid var(--line); padding:6px 0; } }
"""

JS = """
const q=document.getElementById('q'), only=document.getElementById('onlyIssues'), promo=document.getElementById('showPromo');
function apply(){ const s=q.value.trim().toLowerCase();
  document.querySelectorAll('tbody tr[data-kind]').forEach(tr=>{
    if(tr.dataset.kind==='promo'){ tr.style.display=(promo && promo.checked && !s && !only.checked)?'':'none'; return; }
    let ok=true; if(s && !tr.dataset.search.includes(s)) ok=false;
    if(only.checked && tr.dataset.status==='ok') ok=false;
    tr.style.display=ok?'':'none'; }); }
[q,only,promo].filter(Boolean).forEach(el=>el.addEventListener('input',apply));
"""

TABLE_HEAD = ('<table><thead><tr><th class="c-pos">{pos}</th><th class="c-img">Фото (парсер)</th><th>На сайте</th>'
              '<th>Результат парсера</th><th>Объёмы и цены (парсер)</th><th>Тип карточки</th><th>Автопроверка</th></tr></thead><tbody>')

SITE_NOTES = {
    "makeup": "Колонка «На сайте» — данные самого магазина (его API каталога).",
    "douglas": ("Колонка «На сайте» — карточка каталога (что на ней написано) и данные магазина Tealium: объёмы, цены и наличие "
                "со страницы товара, а у товаров с одним объёмом — с карточки. Если парсер сам не открывал страницу товара, "
                "её открыл отчёт — это подписано под названием."),
    "220": ("Колонка «На сайте» — карточка каталога: название, бренд и наличие из данных карточки (widget-data), "
            "цены — те, что видны на карточке. Основная цена — публичная; цена «220.lv PLUS» только для участников "
            "программы лояльности, парсер хранит её как цену с кодом «220.lv PLUS». Объём берётся из названия. "
            "Подарочные наборы из 220.lv не сохраняются (решение от 02.10.2026)."),
    "notino": ("Колонка «На сайте» — карточка каталога (что на ней написано) и данные самого Notino, встроенные в страницы: "
               "у товаров с одним объёмом — из каталога, у товаров с несколькими — цена, наличие и название каждого варианта "
               "со страницы товара (refill Notino помечает в названии варианта). Если парсер сам не открывал страницу товара, "
               "её открыл отчёт — это подписано под названием."),
}


def render_row(r: dict, show_page: bool) -> str:
    pos_cell = r["pos"]
    if show_page:
        pos_cell = (f'<a class="link" href="{e(r["page_url"])}" target="_blank" rel="noopener">'
                    f'стр. {r["page"]}</a><br>№ {r["pos"]}')
    if r["kind"] == "promo":
        return (f'<tr class="promo" data-kind="promo"><td class="c-pos">{pos_cell}</td><td></td>'
                f'<td colspan="5" class="muted">Не товар — {e(r["label"])}{": " + e(r["title"]) if r["title"] else ""}</td></tr>')
    search = f'{r["site_brand"]} {r["site_title"]} ' + " ".join(c["title"] for c in r["cands"])
    status = r["status"]
    # The photo the parser saved (what the site shows), else the site's own.
    image = next((c.get("image_url") for c in r["cands"] if c.get("image_url")), None) or r["image"]
    img = (f'<a href="{e(image)}" target="_blank" rel="noopener"><img src="{e(image)}" loading="lazy" alt=""></a>'
           if image else "")
    site_cell = (
        f'<div class="brand">{e(r["site_brand"])}</div><div>{e(r["site_title"])}</div>'
        f'<div class="muted">{e(r["site_sub"])}</div>'
        + (f'<div class="muted">на карточке: {e(r["card_text"])}</div>' if r.get("card_text") else "")
        + (f'<div class="muted">{e(r["variants_note"])}</div>' if r.get("variants_note") else "")
        + f'<a class="link" href="{e(r["url"])}" target="_blank" rel="noopener">открыть товар ↗</a>'
    )
    if r["cands"]:
        c0 = r["cands"][0]
        is_set = c0.get("card_type") == "gift_set"
        display = c0["title"] if is_set else (
            re.sub(r"\s*\d+(?:[.,]\d+)?\s*(?:ml|l|g|oz)\b.*$", "", c0["title"], flags=re.I) or c0["title"])
        groups = sorted({g["group"] for g in r["db_rows"] if g["group"]})
        group_line = ("в сравнении цен: " + "; ".join(groups)) if groups else "в сравнении цен не участвует"
        parser_cell = (
            f'<div class="brand">{e(c0.get("brand"))}</div><div>{e(display)}</div>'
            f'<div class="muted">тип: {"подарочный набор" if is_set else "духи"} · концентрация: {e(c0.get("concentration") or "—")}</div>'
            f'<div class="muted">{e(group_line)}</div>'
        )
        last_by_vol = {db["volume"]: db["last_price"] for db in r["db_rows"]}

        def price_cell(c: dict) -> str:
            return f'<b>{e(_money(c["price"]))} €</b>' if c["price"] else '<span class="muted">цены нет</span>'

        def price_note(c: dict) -> str:
            """A second line under the volume row (a full-width grid row, so it
            never runs into the stock column)."""
            if c["price"] and c.get("promo_price"):
                text = f'с кодом «{e(c.get("promo_code"))}»: {e(_money(c["promo_price"]))} €'
            elif not c["price"] and last_by_vol.get(c.get("volume")):
                text = f'в базе осталась {e(_money(last_by_vol[c.get("volume")]))} €'
            else:
                return ""
            return f'<span class="vol-note muted">{text}</span>'

        vol_lines = "".join(
            f'<div class="vol"><span>{e(c.get("volume") or "без объёма")}</span>{price_cell(c)}'
            f'<span class="{"yes" if c.get("is_available") else "no"}">{"в наличии" if c.get("is_available") else "нет в наличии"}</span>'
            f'{price_note(c)}</div>'
            for c in r["cands"]
        )
    else:
        label = "Отброшен парсером — правильно" if r["expected_drop"] else "Отброшен парсером"
        parser_cell = f'<div class="{"ok" if r["expected_drop"] else "dropped-label"}">{label}</div><div class="muted">{e(r["drop_reason"])}</div>'
        vol_lines = '<span class="muted">—</span>'
    tags = "".join(f'<span class="tag t-{k}">{e(t)}</span>' for k, t in r["tags"])
    if not r["cands"]:
        check = '<span class="ok">это не парфюм, в базу не попал</span>' if r["expected_drop"] else '<span class="muted">—</span>'
    elif r["issues"]:
        check = '<div class="warn-title">Замечания</div><ul>' + "".join(f"<li>{e(i)}</li>" for i in r["issues"]) + "</ul>"
    else:
        check = '<span class="ok">совпадает с данными сайта</span>'
    return (f'<tr class="st-{status}" data-kind="product" data-status="{status}" data-search="{e(search.lower())}">'
            f'<td class="c-pos">{pos_cell}</td><td class="c-img">{img}</td><td>{site_cell}</td><td>{parser_cell}</td>'
            f'<td>{vol_lines}</td><td>{tags}</td><td>{check}</td></tr>')


def html_page(title: str, subtitle: str, stats: list[tuple[str, object]], note: str, body: str, promo_toggle: bool) -> str:
    stat_html = "".join(f'<div class="stat">{e(k)}: <b>{e(v)}</b></div>' for k, v in stats)
    promo_ctl = ('<label><input type="checkbox" id="showPromo" checked> показывать не-товары (для совпадения позиций)</label>'
                 if promo_toggle else "")
    return f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title><style>{CSS}</style></head><body>
<header>
  <h1>{e(title)}</h1>
  <div class="muted">{subtitle}</div>
  <div class="stats">{stat_html}</div>
  <div class="controls">
    <input type="search" id="q" placeholder="Поиск по бренду или названию">
    <label><input type="checkbox" id="onlyIssues"> только с замечаниями или отброшенные</label>
    {promo_ctl}
  </div>
</header>
<main><div class="note">{note}</div>{body}</main>
<script>{JS}</script></body></html>"""


def render_pages_report(site: str, site_name: str, category_url: str, pages: list[dict], started: datetime) -> str:
    rows = [r for pg in pages for r in pg["rows"]]
    products = [r for r in rows if r["kind"] == "product"]
    saved = [r for r in products if r["cands"]]
    body = []
    for pg in pages:
        n = sum(1 for r in pg["rows"] if r["kind"] == "product")
        body.append(
            f'<section class="page"><div class="page-head"><h2>Страница {pg["page"]}</h2><span class="muted">{n} товаров</span>'
            f'<a class="btn" href="{e(pg["page_url"])}" target="_blank" rel="noopener">Открыть эту страницу на сайте ↗</a></div>'
            + TABLE_HEAD.format(pos="№") + "".join(render_row(r, False) for r in pg["rows"]) + "</tbody></table></section>"
        )
    stats = [
        ("Страниц", len(pages)), ("Товаров на страницах", len(products)),
        ("Сохранено парсером", f'{len(saved)} ({sum(len(r["cands"]) for r in saved)} записей)'),
        ("Отброшено", f'{len(products) - len(saved)} (из них не парфюм: {sum(1 for r in products if not r["cands"] and r["expected_drop"])})'),
        ("С замечаниями автопроверки", sum(1 for r in products if r["status"] != "ok")),
    ]
    if len(rows) > len(products):
        stats.append(("Не товары (баннеры, отзывы)", len(rows) - len(products)))
    note = ("Как проверять: открой страницу на сайте кнопкой справа и иди по карточкам сверху вниз. Номер в колонке «№» — позиция карточки в выдаче магазина. "
            + SITE_NOTES.get(site, "") + " «Результат парсера» и «Объёмы и цены» — то, что парсер записал в базу. "
            "«Автопроверка» сравнивает их автоматически, но окончательное решение — за твоей ручной проверкой. "
            "Парсер пока не сохраняет старую цену до скидки — пометка «скидка» в «Типе карточки» взята с сайта.")
    subtitle = (f'Запуск: {started:%d.%m.%Y %H:%M} · Каталог: <a class="link" href="{e(category_url)}" target="_blank" rel="noopener">{e(category_url)}</a>')
    return html_page(f"Проверка парсера — {site_name}", subtitle, stats, note, "".join(body), promo_toggle=len(rows) > len(products))


def render_variations_report(site: str, site_name: str, category_url: str, sections: list[dict], sample_info: dict, started: datetime) -> str:
    summary_rows = []
    body = []
    for s in sections:
        shown = s["rows"]
        flagged = sum(1 for r in shown if r["status"] != "ok")
        if not shown:
            verdict = '<span class="muted">в выборке не найдено</span>'
        elif flagged:
            verdict = f'<span class="warn-title">замечания: {flagged} из {len(shown)}</span>'
        else:
            verdict = f'<span class="ok">без замечаний ({len(shown)} из {len(shown)})</span>'
        summary_rows.append(f'<tr><td><a class="link" href="#k-{s["key"]}">{e(s["title"])}</a></td>'
                            f'<td>{s["found"]}</td><td>{len(shown)}</td><td>{verdict}</td></tr>')
        section = [f'<section class="page" id="k-{s["key"]}"><div class="page-head"><h2>{e(s["title"])}</h2>'
                   f'<span class="muted">в выборке: {s["found"]} · показано: {len(shown)}</span></div>'
                   f'<div class="expect"><b>Как должно быть:</b> {e(s["expect"])}</div>']
        if shown:
            section.append(TABLE_HEAD.format(pos="Где") + "".join(render_row(r, True) for r in shown) + "</tbody></table>")
        else:
            section.append('<div class="expect muted">Таких карточек в просмотренной части каталога нет.</div>')
        section.append("</section>")
        body.append("".join(section))
    summary = ('<section class="page"><div class="page-head"><h2>Сводка по типам карточек</h2></div>'
               '<table class="summary"><thead><tr><th>Тип карточки</th><th>Найдено в выборке</th><th>Показано</th><th>Итог автопроверки</th></tr></thead>'
               f'<tbody>{"".join(summary_rows)}</tbody></table></section>')
    viewed = "все" if sample_info["step"] == 1 else f'каждая {sample_info["step"]}-я'
    stats = [
        ("Страниц каталога", sample_info["total_pages"]),
        (f"Просмотрено ({viewed})", sample_info["sampled_pages"]),
        ("Товаров в выборке", sample_info["sampled_products"]),
        ("Спарсено страниц для примеров", len(sample_info["scraped_pages"])),
    ]
    note = ("Здесь собраны примеры каждого типа карточек из всего каталога. У каждого примера в колонке «Где» — ссылка на страницу каталога и позиция на ней, "
            "в колонке «На сайте» — ссылка на сам товар. " + SITE_NOTES.get(site, "") + " Проверь, что парсер обработал каждый тип так, как написано в «Как должно быть». "
            "Страницы со всеми примерами спарсены настоящим парсером: " + ", ".join(str(p) for p in sample_info["scraped_pages"]) + ".")
    subtitle = (f'Запуск: {started:%d.%m.%Y %H:%M} · Каталог: <a class="link" href="{e(category_url)}" target="_blank" rel="noopener">{e(category_url)}</a>')
    return html_page(f"Вариации карточек — {site_name}", subtitle, stats, note, summary + "".join(body), promo_toggle=False)


# ── Modes ────────────────────────────────────────────────────────────────────

async def mode_first_pages(site: str, target: dict, pages: int, started: datetime) -> str:
    cap = ReviewCapture()
    await run_first_pages(site, target, cap, pages)
    model = await evaluate_pages(site_pages(site, cap, target["url"])[:pages], cap)
    return render_pages_report(site, target.get("site", ""), target["url"], model, started)


async def mode_selected_pages(site: str, target: dict, page_numbers: list[int], started: datetime) -> str:
    cap = ReviewCapture()
    if site == "makeup":
        await run_makeup_pages(target, cap, page_numbers)
    elif site == "220":
        await run_douglas_pages(target, cap, page_numbers, s220_page_url)
    else:
        await run_douglas_pages(target, cap, page_numbers)
    model = await evaluate_pages(site_pages(site, cap, target["url"]), cap)
    return render_pages_report(site, target.get("site", ""), target["url"], model, started)


def choose_pages(sampled: list[dict], per_kind: int, max_pages: int) -> list[int]:
    by_page: dict[int, dict[str, int]] = {}
    for s in sampled:
        for k in s["kinds"]:
            by_page.setdefault(s["page"], {}).setdefault(k, 0)
            by_page[s["page"]][k] += 1
    need = {k: per_kind for k, _, _ in VARIATION_KINDS}
    chosen: list[int] = []
    while len(chosen) < max_pages and any(v > 0 for v in need.values()):
        best, best_score = None, 0
        for page, counts in by_page.items():
            if page in chosen:
                continue
            score = sum(min(need[k], c) * (3 if need[k] == per_kind else 1) for k, c in counts.items() if k in need)
            if score > best_score:
                best, best_score = page, score
        if best is None:
            break
        chosen.append(best)
        for k, c in by_page[best].items():
            if k in need:
                need[k] = max(0, need[k] - c)
    return sorted(chosen)


async def mode_variations(site: str, target: dict, step: int, per_kind: int, max_pages: int, started: datetime) -> str:
    logger.info(f"[REVIEW] sampling the catalog (every {step} page(s))")
    if site == "makeup":
        sampled, total_pages = await sample_makeup_catalog(target["url"], step)
    elif site == "220":
        sampled, total_pages = await sample_220_catalog(target["url"], step)
    else:
        sampled, total_pages = await sample_douglas_catalog(target["url"], step)
    found = {k: sum(1 for s in sampled if k in s["kinds"]) for k, _, _ in VARIATION_KINDS}
    pages = choose_pages(sampled, per_kind, max_pages)
    logger.info(f"[REVIEW] kinds in sample: {found}; scraping pages {pages}")

    cap = ReviewCapture()
    if site == "makeup":
        await run_makeup_pages(target, cap, pages)
    elif site == "220":
        await run_douglas_pages(target, cap, pages, s220_page_url)
    else:
        await run_douglas_pages(target, cap, pages)
    model = await evaluate_pages(site_pages(site, cap, target["url"]), cap)
    products = [r for pg in model for r in pg["rows"] if r["kind"] == "product"]

    sections = []
    for key, title, expect in VARIATION_KINDS:
        matching = [r for r in products if key in r["kinds"]]
        # flagged examples first — they need the closest look
        matching.sort(key=lambda r: (r["status"] == "ok", r["page"], r["pos"]))
        sections.append({"key": key, "title": title, "expect": expect,
                         "found": found.get(key, 0), "rows": matching[:per_kind]})
    info = {"total_pages": total_pages, "step": step, "sampled_pages": len({s["page"] for s in sampled}),
            "sampled_products": len(sampled), "scraped_pages": pages}
    return render_variations_report(site, target.get("site", ""), target["url"], sections, info, started)


async def main() -> None:
    ap = argparse.ArgumentParser(description="Run the scraper on catalog pages and write an HTML review report.")
    ap.add_argument("site", help="site key: " + ", ".join(sorted(SUPPORTED_SITES)))
    ap.add_argument("--pages", type=int, default=3, help="first N pages (default mode)")
    ap.add_argument("--only", default=None, help="comma-separated catalog page numbers, e.g. 5,8")
    ap.add_argument("--variations", action="store_true", help="find and check every kind of product card")
    ap.add_argument("--step", type=int, default=None, help="variations: sample every N-th catalog page")
    ap.add_argument("--per-kind", type=int, default=4, help="variations: examples shown per card kind")
    ap.add_argument("--max-pages", type=int, default=8, help="variations: max pages to scrape for examples")
    args = ap.parse_args()
    site = args.site.lower()
    if site not in SUPPORTED_SITES:
        raise SystemExit(f"Review report is implemented for: {', '.join(sorted(SUPPORTED_SITES))}")
    if site == "notino" and (args.variations or args.only):
        raise SystemExit("notino: only the first-pages mode (--pages N) is implemented so far")

    target = find_target(site)
    started = datetime.now()
    domain = domain_of(target["url"])
    if args.variations:
        step = args.step or DEFAULT_STEP[site]
        html_text = await mode_variations(site, target, step, args.per_kind, args.max_pages, started)
        name = f"scrape_variations_{domain}_{started:%Y-%m-%d_%H%M}.html"
    elif args.only:
        page_numbers = sorted({int(x) for x in args.only.split(",") if x.strip()})
        html_text = await mode_selected_pages(site, target, page_numbers, started)
        name = f"scrape_review_{domain}_p{'-'.join(map(str, page_numbers))}_{started:%Y-%m-%d_%H%M}.html"
    else:
        html_text = await mode_first_pages(site, target, args.pages, started)
        name = f"scrape_review_{domain}_{started:%Y-%m-%d_%H%M}.html"
    os.makedirs(REPORTS_DIR, exist_ok=True)
    out = os.path.join(REPORTS_DIR, name)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html_text)
    logger.success(f"[REVIEW] report written: {out}")


if __name__ == "__main__":
    asyncio.run(main())
