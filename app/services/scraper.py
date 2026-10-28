import asyncio
import random
import sys
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from parsel import Selector
from loguru import logger
from sqlmodel import select
from sqlalchemy import or_
from urllib.parse import urljoin, urlparse

from app.domain.models import ScrapingRule, Product, PriceHistory, SharedPattern, ProductGroup
from app.core.client import stealth_client
from app.core.config import settings
from app.core.constants import (
    VERIFIED_FAST_DOMAINS,
    DOMAIN_DEEP_DIVE_CONFIG,
    PRODUCT_BLACKLIST,
    FALLBACK_CONTAINER_CSS,
    FALLBACK_TITLE_CSS,
    MAX_PLAUSIBLE_PRICE,
)

# Chrome errors that mean "this computer is offline", not "the shop refused".
_NETWORK_DOWN = re.compile(
    r"ERR_NAME_NOT_RESOLVED|ERR_INTERNET_DISCONNECTED|ERR_NETWORK_CHANGED|ERR_ADDRESS_UNREACHABLE"
)


async def _wait_for_network(url: str, max_wait: int = 300) -> bool:
    """Waits until the shop's host name resolves again. True when it does."""
    import socket
    import time

    host = urlparse(url).hostname
    logger.warning(f"🌐 No network (DNS) — waiting up to {max_wait} s for it to return: {host}")
    end = time.monotonic() + max_wait
    while time.monotonic() < end:
        try:
            await asyncio.to_thread(socket.getaddrinfo, host, 443)
            logger.info(f"🌐 Network is back: {host}")
            return True
        except OSError:
            await asyncio.sleep(5)
    logger.error(f"🌐 Network did not return within {max_wait} s")
    return False


@dataclass
class ScrapedItem:
    title: str
    price: Optional[Decimal]  # None — price unknown (out of stock, no price shown)
    availability: str
    url: str
    image_url: Optional[str] = None
    is_valid: bool = True
    validation_error: str = ""


class ScraperService:
    # Domains whose generic detail selectors failed during the current run.
    detail_skip_domains: set = set()

    def parse_price(self, price_text: str) -> Decimal:
        if not price_text: return Decimal("0.00")
        # Removing currencies, spaces, non-breaking spaces
        clean = re.sub(r'[^\d.,]', '', price_text)
        clean = clean.replace(',', '.')
        if clean.count('.') > 1: clean = clean.replace('.', '', clean.count('.') - 1)
        try: 
            val = Decimal(clean)
            return val.quantize(Decimal("0.01"))
        except: return Decimal("0.00")

    def extract_clean_text(self, element: Selector) -> str:
        if not element: return ""
        return element.xpath('string(.)').get().strip()

    def validate_dataset(self, items: list[ScrapedItem]) -> dict:
        """
        Checks collected data quality.
        Returns 'health' report of the set.
        """
        if not items:
            return {"score": 0.0, "error": "No items found", "is_healthy": False}

        total = len(items)
        # An out-of-stock item legitimately has no price; only an in-stock item
        # without one points at a broken selector.
        zero_prices = sum(1 for i in items if i.availability != "No" and (i.price is None or i.price <= 0))
        short_titles = sum(1 for i in items if len(i.title) < 5)
        
        # Penalty points
        penalty = (zero_prices / total) * 0.7  # Prices are most important
        penalty += (short_titles / total) * 0.3 # Titles are also important
        
        score = max(0.0, 1.0 - penalty)
        
        report = {
            "total": total,
            "zero_prices": zero_prices,
            "short_titles": short_titles,
            "score": round(score, 2),
            "is_healthy": score > 0.7 and total >= 10
        }
        
        if score <= 0.7:
            report["error"] = "Low data quality: too many zero prices or bad titles"
        elif total < 10:
            report["error"] = "Low quantity: less than 10 items found"
            
        return report

    async def learn_from_success(self, session, rule: ScrapingRule):
        """
        Saves successful selectors to the shared knowledge base.
        """
        patterns = [
            ('container', rule.container_css),
            ('title', rule.title_css),
            ('price', rule.price_css),
            ('image', rule.image_css),
            ('next_page', rule.next_page_css)
        ]
        
        from datetime import datetime
        for p_type, selector in patterns:
            if not selector: continue
            
            # Searching if this pattern already exists
            stmt = select(SharedPattern).where(SharedPattern.css_selector == selector)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            
            if existing:
                existing.success_count += 1
                existing.last_used = datetime.utcnow()
                session.add(existing)
            else:
                new_p = SharedPattern(pattern_type=p_type, css_selector=selector)
                session.add(new_p)
        
        await session.commit()
        logger.info(f"🧠 Site patterns {rule.domain} added to knowledge base.")


    def _find_next_page_fallback(self, sel: Selector, current_url: str) -> str | None:
        def clean_href(href: str | None) -> str | None:
            if not href: return None
            if href.startswith('javascript:') or href == '#': return None
            from urllib.parse import urljoin, urlparse
            if bool(urlparse(href).netloc): return href
            parsed_base = urlparse(current_url)
            base_root = f"{parsed_base.scheme}://{parsed_base.netloc}"
            return urljoin(base_root, href) if href.startswith('/') else urljoin(current_url, href)

        def is_valid_pagination(href: str) -> bool:
            if not href: return False
            junk = ['/news/', '/product/', '/ads/', '/cart/', '/login/', '/auth/']
            if any(j in href.lower() for j in junk): return False
            return True

        # 1. NUMERIC INCREMENT (Best for Makeup.lv)
        active_nodes = sel.xpath("//li[contains(@class, 'page') and (not(descendant::a) or contains(@class, 'active') or contains(@class, 'current'))]//text()[normalize-space()]").getall()
        if not active_nodes:
            active_nodes = sel.xpath("//input[@checked]/following-sibling::label//text()").getall()

        current_page_num = None
        for txt in active_nodes:
            if txt.strip().isdigit():
                current_page_num = int(txt.strip())
                break

        if current_page_num:
            next_num = current_page_num + 1
            next_num_link = sel.xpath(f"//li[contains(@class, 'page')]//a[text()='{next_num}']/@href").get()
            if not next_num_link:
                 next_num_link = sel.xpath(f"//a[text()='{next_num}']/@href").get()

            candidate = clean_href(next_num_link)
            if candidate and is_valid_pagination(candidate):
                logger.info(f"🔢 Found next page by incrementing: {current_page_num} -> {next_num} ({candidate})")
                return candidate

        # 2. SIBLING LOGIC
        active_li = sel.xpath("//li[contains(@class, 'page') and (not(descendant::a) or contains(@class, 'active'))]")
        if not active_li:
            active_li = sel.xpath("//input[@checked or @checked='checked']/ancestor::li")
        if active_li:
            next_link = active_li.xpath("./following-sibling::li[descendant::a][1]//a/@href").get()
            candidate = clean_href(next_link)
            if candidate and is_valid_pagination(candidate):
                logger.info(f"⏭️ Found next page via sibling logic: {candidate}")
                return candidate

        # 3. URL-PATTERN FALLBACK (SPA sites where pagination is JS-rendered)
        # If site supports `?page=N` query param, just increment it. The outer
        # loop's seen_page_signatures will break us out when the site returns
        # the same content (i.e. we've passed the real last page).
        from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
        parsed = urlparse(current_url)
        params = parse_qs(parsed.query)
        current_page = 1
        if "page" in params:
            try:
                current_page = int(params["page"][0])
            except (ValueError, IndexError):
                pass
        next_page_num = current_page + 1
        params["page"] = [str(next_page_num)]
        new_query = urlencode(params, doseq=True)
        candidate = urlunparse(parsed._replace(query=new_query))
        logger.info(f"🔢 URL-pattern fallback: trying ?page={next_page_num} → {candidate}")
        return candidate

    def _try_selectors(self, source: Selector, css_list: str) -> tuple[list[Selector], str | None]:
        if not css_list: return [], None
        selectors = [s.strip() for s in css_list.split(',')]
        for selector in selectors:
            try:
                el = source.css(selector)
                if el: return el, selector
            except: continue
        return [], None

    def _extract_variants(self, card: Selector, base_title: str) -> list[dict]:
        """
        Attempts to find hidden variants (e.g., different volumes) inside the card.
        Currently highly optimized for Makeup.lv JSON structure.
        """
        import json
        variants = []
        
        # 1. Search for embedded JSON
        script_text = card.css('script[type="application/json"]::text').get()
        if script_text:
            try:
                data = json.loads(script_text)
                # Structure: {"variantsData": {"ID": {"price": X, "value": "50 ml"}}}
                v_data = data.get("variantsData")
                if v_data and isinstance(v_data, dict):
                    for v_id, info in v_data.items():
                        volume = info.get("value", "")
                        price = self.parse_price(str(info.get("price", "0")))
                        
                        # Use a common title format: Base Title - Volume
                        full_title = f"{base_title} - {volume}" if volume else base_title
                        
                        variants.append({
                            "title": full_title,
                            "price": price,
                            "variant_id": v_id
                        })
                    return variants
            except Exception as e:
                logger.debug(f"JSON Variant parse error: {e}")
        
        return []
    
    async def _scrape_network_variants(self, url: str) -> list[dict]:
        """notino.lv product page: select every variant and read the shop's own
        tracking request `/api/tracking/web/view/detail`. Notino sends it for the
        variant shown on load and again for each variant the user selects; it
        carries that variant's size, regular price, stock and — when a promo code
        applies — attributes.VoucherDiscount (the price with the code, the code).

        The consent overlay (Usercentrics) covers the page and swallows clicks,
        so it is removed from the DOM first; no consent is given."""
        from app.core.browser import browser_manager
        from app.services.normalizer import volume_qualifier

        logger.info(f"🕷️ [Network Intercept] Deep dive: {url}")
        details: dict[str, dict] = {}  # variant id → its detail payload
        labels: dict[str, str] = {}    # variant id → text of its button ("150 ml Uzpilde", "… refill")
        apollo: dict[str, dict] = {}   # variant id → the page state's own record of it

        def handle_request(request):
            if request.method != "POST" or "/api/tracking/web/view/detail" not in request.url:
                return
            try:
                data = request.post_data_json
            except Exception:
                return
            if isinstance(data, dict) and data.get("id"):
                details[str(data["id"])] = data

        context = await browser_manager.get_context()
        page = await context.new_page()
        page.on("request", handle_request)
        try:
            await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,ico}", lambda route: route.abort())
            failures = outages = 0
            while True:
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    break
                except Exception as e:
                    # The PC lost its network (Wi-Fi reconnecting after sleep): wait
                    # for it instead of spending the product's retries on it.
                    if outages < 3 and _NETWORK_DOWN.search(str(e)):
                        outages += 1
                        if await _wait_for_network(url):
                            continue
                    failures += 1
                    if failures == 2:  # a dropped connection is usually gone on the second try
                        raise
                    logger.warning(f"Notino page load failed ({e.__class__.__name__}), retrying: {url}")
                    await asyncio.sleep(5)
            if not await browser_manager.wait_for_notino_content(page):
                return []
            try:  # the consent overlay is injected late, after the page renders
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            remove_overlay = "() => document.querySelector('#usercentrics-cmp-ui')?.remove()"

            links = page.locator(
                "[data-testid='pd-variants-thumbnail'] a[data-testid^='pd-variant-'], "
                "[data-testid='pd-variants-tile'] a[data-testid^='pd-variant-'], "
                "[data-testid='pd-variants-color-picker'] a[data-testid^='pd-variant-']"
            )
            for i in range(await links.count()):
                link = links.nth(i)
                try:  # one slow or re-rendered button must not lose the whole product
                    vid = (await link.get_attribute("data-testid", timeout=5000) or "").removeprefix("pd-variant-")
                    alt = ""
                    if await link.locator("img").count():
                        alt = await link.locator("img").first.get_attribute("alt", timeout=5000) or ""
                    labels[vid] = f"{await link.inner_text(timeout=5000)} {alt}"
                except Exception as e:
                    logger.debug(f"Notino variant button {i}: unreadable: {e}")
                    continue
                if vid in details:
                    continue  # the variant shown on load is already reported
                try:
                    await page.evaluate(remove_overlay)
                    await link.click(timeout=5000)
                except Exception as e:
                    logger.debug(f"Notino variant {vid}: click failed: {e}")
                    continue
                for _ in range(25):  # up to 5 s for its detail request
                    if vid in details:
                        break
                    await asyncio.sleep(0.2)
            # A product without variant buttons reports its only variant on load.
            for _ in range(25):
                if details:
                    break
                await asyncio.sleep(0.2)
        except Exception as e:
            logger.error(f"Network intercept failed for {url}: {e}")
        finally:
            # Not every button names its pack ("125 ml Uzpilde"); the page's own
            # state names every variant — and still describes them when a click failed.
            try:
                import json
                raw = await page.locator("script#__APOLLO_STATE__").first.text_content(timeout=2000)
                for key, v in json.loads(raw or "{}").items():
                    if key.startswith("CatalogVariant:") and isinstance(v, dict) and v.get("webId"):
                        vid = str(v["webId"])
                        names = (v.get("additionalInfo"), v.get("variantName"), v.get("variantType"))
                        labels[vid] = " ".join(x for x in (labels.get(vid), *names) if x)
                        apollo[vid] = v
            except Exception as e:
                logger.debug(f"Notino variant names unavailable: {e}")
            # The whole context, not just the page: an open context keeps its
            # connections (New Relic beacons) and thousands of them run Windows out of ports.
            await context.close()

        variants = []
        for vid, d in details.items():
            size, unit, price = d.get("size"), d.get("sizeUnit"), d.get("price")
            if not size or not unit or not price:
                continue
            suffix = f"{float(size):g} {unit}"
            qualifier = volume_qualifier(labels.get(vid))
            if qualifier:
                suffix += f" {qualifier}"
            voucher = (d.get("attributes") or {}).get("VoucherDiscount") or {}
            promo = voucher.get("discountedPrice")
            variants.append({
                "title_suffix": suffix,
                "price": Decimal(str(price)).quantize(Decimal("0.01")),
                "is_available": d.get("stockQuantity") != "outOfStock",
                "promo_price": Decimal(str(promo)).quantize(Decimal("0.01")) if promo else None,
                "promo_code": voucher.get("code") if promo else None,
            })
        # A variant whose click or tracking request failed is still described in
        # the page state (volume, price, stock) — without the promo-code price.
        for vid, v in apollo.items():
            if vid in details:
                continue
            m = re.search(r"(\d+(?:[.,]\d+)?)\s*(ml|g|l)\b", v.get("additionalInfo") or "", re.IGNORECASE)
            price = (v.get("price") or {}).get("value")
            if not m or not price:
                continue
            suffix = f"{float(m.group(1).replace(',', '.')):g} {m.group(2).lower()}"
            qualifier = volume_qualifier(labels.get(vid))
            if qualifier:
                suffix += f" {qualifier}"
            variants.append({
                "title_suffix": suffix,
                "price": Decimal(str(price)).quantize(Decimal("0.01")),
                "is_available": (v.get("availability") or {}).get("state") == "CanBeBought",
                "promo_price": None,
                "promo_code": None,
            })
        logger.info(f"  🔎 Notino variants: {[(v['title_suffix'], str(v['price']), v['is_available'], v['promo_code']) for v in variants]}")
        return variants

    async def scrape_product_details(self, url: str, rule: ScrapingRule, session=None, browser_context=None) -> list[dict]:
        """
        Fetches the product page and extracts all available variants (volumes/prices).
        Uses AI to learn the structure if not already known, or Network Interception for known advanced sites.
        """
        logger.info(f"🔍 Deep dive: {url}")
        
        # Sites like Notino block StealthClient on detail pages, use Browser directly
        # AND Notino has complex variants that are perfectly exposed in network analytics.
        if "notino.lv" in url:
             logger.info("⚡ Notino detected. Using Universal Network Interceptor (BFF).")
             network_variants = await self._scrape_network_variants(url)
             if not network_variants:
                 # A slow page sometimes answers nothing at all; one more try
                 # usually gets it (gift sets without a volume stay empty).
                 await asyncio.sleep(random.uniform(3.0, 5.0))
                 network_variants = await self._scrape_network_variants(url)
             if network_variants:
                 logger.success(f"🎯 Network intercept extracted {len(network_variants)} variants flawlessly.")
             else:
                 # The generic DOM/AI path cannot read Notino; trying it only ends
                 # in a stored "SKIP" that switches deep dives off for good.
                 logger.warning(f"Notino: no variants read from {url}")
             return network_variants

        html = None
        is_verified = any(d in url for d in VERIFIED_FAST_DOMAINS)
        
        if "notino.lv" in url:
            from app.core.browser import browser_manager
            resp = await browser_manager.get_page_content(url, fast_mode=True, context=browser_context, verified_domain=False)
            html = resp["html"] if resp else None
        else:
            html = await stealth_client.get_page(url)
            if not html or "captcha" in html.lower() or "403" in str(html) or "202 Accepted" in str(html):
                 from app.core.browser import browser_manager
                 resp = await browser_manager.get_page_content(url, fast_mode=True, context=browser_context, verified_domain=is_verified)
                 html = resp["html"] if resp else None
             
        if not html: return []
        
        if "douglas.lv" in url:
            logger.info("⚡ Douglas detected. Parsing Tealium JSON payloads directly from SSR HTML.")
            try:
                import json
                import html as html_lib
                import re
                
                tealium_matches = re.finditer(r'data-tealium-info-view.*?=.*?(\[.*?\]|{.*?})', html, re.DOTALL)
                douglas_variants = []
                seen_vols = set()
                page_master = None

                for match in tealium_matches:
                    text_match = match.group(1)
                    text_unescaped = html_lib.unescape(text_match)
                    try:
                        data = json.loads(text_unescaped)

                        p_price_list = data.get("primary_product_price", [])
                        v_name_list = data.get("primary_product_variant_name", [])
                        stock_list = data.get("primary_product_availability_status", [])
                        id_list = data.get("primary_product_id", [])
                        # Every variant of the page's product shares one master id;
                        # anything else on the page is another product.
                        master = (data.get("primary_product_master_id") or [None])[0]
                        if page_master is None:
                            page_master = master
                        elif master and master != page_master:
                            continue

                        for i in range(len(p_price_list)):
                            p_price_str = str(p_price_list[i]) if p_price_list else "0"
                            p_price = self.parse_price(p_price_str)
                            
                            p_vol = str(v_name_list[i]) if len(v_name_list) > i and v_name_list[i] else ""
                            p_stock = str(stock_list[i]).lower() if len(stock_list) > i and stock_list[i] else ""
                            
                            if p_price > 0 and p_vol not in seen_vols:
                                is_avail = True
                                if "out of stock" in p_stock or "nav pieejams" in p_stock or "soon back" in p_stock or "drīz tirdzniecībā" in p_stock:
                                    is_avail = False

                                seen_vols.add(p_vol)
                                douglas_variants.append({
                                    "title_suffix": p_vol,
                                    "price": p_price,
                                    "is_available": is_avail,
                                    # The variant's own ?item= id: the catalog card links to
                                    # whichever variant it shows, which changes between runs.
                                    "item_id": str(id_list[i]) if len(id_list) > i and id_list[i] else None,
                                })
                                # DEBUG (S20.1): show what Tealium returns so we can see why all
                                # variants of one product end up with the same normalized volume.
                                logger.info(f"  🔎 Tealium variant: title_suffix={p_vol!r}  price={p_price}  avail={is_avail}")
                    except Exception as e:
                        logger.debug(f"Douglas Tealium JSON parse error: {e}")
                        continue
                        
                if douglas_variants:
                    logger.success(f"🎯 Douglas Tealium extracted {len(douglas_variants)} variants natively.")
                    return douglas_variants
                else:
                    logger.warning("Douglas Tealium parsing yielded 0 variants. Falling back to DOM parsing.")
            except Exception as e:
                logger.error(f"Douglas specific scrape error: {e}")
        
        # --- SELF-LEARNING PHASE: If we don't have detail selectors, ask AI ---
        if not rule.detail_variant_selector and session:
            logger.warning(f"🧠 [Autonomous] Learning detail structure for {rule.domain}...")
            from app.services.ai_generator import ai_generator
            detail_data = await ai_generator.generate_detail_rule(url, html)
            
            if detail_data.get("variant_container_css"):
                rule.detail_variant_selector = detail_data.get("variant_container_css")
                rule.detail_variant_name_css = detail_data.get("variant_name_css")
                rule.detail_variant_price_css = detail_data.get("variant_price_css")
                
                # Update rule in session
                session.add(rule)
                await session.commit()
                logger.success(f"🧠 [Autonomous] Saved detail rules for {rule.domain}")
            else:
                # AI found no variants: don't ask again in this run. Not stored in the
                # rule — a stored "SKIP" would switch deep dives off for every later run.
                self.detail_skip_domains.add(rule.domain)

        sel = Selector(text=html)
        variants = []
        
        # 1. Use AI-generated or manual selectors
        v_selector = rule.detail_variant_selector
        if v_selector and v_selector != "SKIP":
            nodes = sel.css(v_selector)
            if not nodes:
                logger.debug(f"⚠️ Selector {v_selector} found 0 nodes on {url}. HTML length: {len(html)}")

            for node in nodes:
                # Use learned selectors or fallbacks
                name_css = rule.detail_variant_name_css or ".volume, .name, [data-testid*='name']"
                price_css = rule.detail_variant_price_css or ".price, [data-testid*='price']"
                
                v_title = self.extract_clean_text(node.css(name_css))
                v_price_text = self.extract_clean_text(node.css(price_css))
                v_price = self.parse_price(v_price_text)
                
                if v_title and v_price > 0:
                    variants.append({
                        "title_suffix": v_title,
                        "price": v_price,
                        "is_available": True
                    })
            
            # --- SELF-HEALING: If selector exists but finds nothing, it's stale/wrong ---
            if not variants and nodes:
                # If we found nodes but no valid data inside, the internal selectors (name/price) are wrong
                pass
            elif not nodes and v_selector != "SKIP":
                logger.warning(f"🚩 Selector {v_selector} is useless for {rule.domain}. Disabling Deep Dive for this run.")
                self.detail_skip_domains.add(rule.domain)
        
        # 2. IF 0 VARIANTS: Try one-time AI learning (disabled because it causes infinite loops)
        # if not variants and session:
        #    logger.warning(f"🤔 No variants found with stored rule for {url}. Trying one-time AI assist...")
        #    from app.services.ai_generator import ai_generator
        #    try:
        #        one_time_data = await ai_generator.generate_detail_rule(url, html)
        #        v_selector = one_time_data.get("variant_container_css")
        #        if v_selector:
        #            nodes = sel.css(v_selector)
        #            for node in nodes:
        #                name_css = one_time_data.get("variant_name_css") or ".volume, .name"
        #                price_css = one_time_data.get("variant_price_css") or ".price"
        #                name_el, _ = self._try_selectors(node, name_css)
        #                price_el, _ = self._try_selectors(node, price_css)
        #                name_text = self.extract_clean_text(name_el)
        #                price_text = self.extract_clean_text(price_el)
        #                p_val = self.parse_price(price_text)
        #                if name_text:
        #                    variants.append({
        #                        "title_suffix": name_text,
        #                        "price": p_val,
        #                        "is_available": p_val > 0
        #                    })
        #    except Exception as e:
        #        logger.error(f"AI Fallback failed: {e}")

        # 3. Universal Fallback: If no variants, try single main price
        if not variants:
            price_sel = rule.detail_variant_price_css or rule.price_css or "[data-testid*='price'], .price"
            main_price_text = self.extract_clean_text(sel.css(price_sel))
            main_price = self.parse_price(main_price_text)
            if main_price > 0:
                variants.append({
                    "title_suffix": "",
                    "price": main_price,
                    "is_available": True
                })
                
        return variants

    async def _scrape_notino_catalog(
        self,
        session,
        rule,
        start_url: str,
        max_items: int,
        group_id,
        intent,
        site_name_ui,
    ) -> list:
        """Notino catalog scraper using a single persistent Playwright page.

        Cloudflare blocks repeated new-page navigations to the same Notino URL
        within the same browser session. The fix: open ONE page, scrape it, then
        click the nextPage chevron on THAT SAME page — CF never re-challenges.
        """
        from parsel import Selector as ScrapySelector
        from app.core.browser import browser_manager
        from app.services.normalizer import perfume_normalizer

        ctx = await browser_manager.get_context()
        final_scraped_items: list = []

        from app.services.ui import get_dashboard
        db = get_dashboard()

        page = await ctx.new_page()
        # Pages 2+ are loaded by the "next" button through Notino's navigation
        # API; its JSON answer holds the new page's product list.
        nav_listings: list = []

        async def _keep_listing(resp):
            if "/api/navigation/navigation/" in resp.url:
                try:
                    nav_listings.append(await resp.json())
                except Exception:
                    pass

        page.on("response", lambda resp: asyncio.ensure_future(_keep_listing(resp)))
        try:
            await page.route(
                "**/*.{png,jpg,jpeg,gif,webp,svg,ico}",
                lambda route: route.abort()
            )
            # No playwright_stealth on this tab: its patches break Notino's
            # "next page" button (the click does nothing). The context's own
            # init script already covers the basics.

            logger.info(f"🕷️ Notino persistent-page: loading {start_url}")
            await page.goto(start_url, wait_until="domcontentloaded", timeout=60000)

            # Remove CMP overlay so it never blocks clicks
            async def _dismiss_cmp():
                try:
                    await page.evaluate(
                        "() => { const e = document.querySelector('#usercentrics-cmp-ui'); if (e) e.remove(); }"
                    )
                except Exception:
                    pass

            await _dismiss_cmp()

            # Wait for React to fully render page 1
            try:
                await page.wait_for_load_state("networkidle", timeout=12000)
            except Exception:
                await asyncio.sleep(6)
                
            # Extract dynamic pagination URL format from React state
            html_init = await page.content()
            import re
            notino_pagination_fmt = None
            match = re.search(r'"pageUrl"\s*:\s*"([^"]+\{pageNumber\}[^"]+)"', html_init)
            if match:
                notino_pagination_fmt = match.group(1)
                logger.info(f"🔗 Extracted Notino pagination format: {notino_pagination_fmt}")
            else:
                logger.warning("⚠️ Could not extract Notino pagination format. Fallback may fail.")
            pages_match = re.search(r'"numberOfPages"\s*:\s*(\d+)', html_init)
            total_pages = int(pages_match.group(1)) if pages_match else None

            NEXT_BTN_SEL = "div.nextPage[data-testid='page-button-wrapper']"
            page_number = 0
            processed_cards = 0
            seen_page_signatures: set = set()
            
            # Variables for fetching next pages directly via browser_manager
            current_html_override = None
            current_url_override = None

            while processed_cards < max_items:
                page_number += 1
                if db and site_name_ui:
                    db.update_status(site_name_ui, f"Loading Page {page_number}")

                if current_html_override:
                    html = current_html_override
                    current_url = current_url_override
                    current_html_override = None
                else:
                    html = await page.content()
                    current_url = page.url
                    
                sel = ScrapySelector(text=html)

                cards, _ = self._try_selectors(sel, rule.container_css)
                if not cards:
                    logger.error(f"❌ Notino page {page_number}: no cards. Stopping.")
                    break

                logger.info(f"🔮 [Page {page_number}] Cards: {len(cards)}")
                # Page 1's list is embedded in the HTML; later pages come from the
                # navigation API (the embedded JSON keeps page 1's data).
                listing = {}
                if page_number > 1 and nav_listings:
                    listing = self._notino_listing_data(nav_listings[-1], current_url)
                if not listing:
                    listing = self._notino_listing(html, current_url)

                # Loop detection
                page_hrefs = frozenset(
                    card.css("a::attr(href)").get() or "" for card in cards
                ) - {""}
                if page_hrefs and page_hrefs in seen_page_signatures:
                    logger.info("🔁 Notino loop detected — same card set. Stopping.")
                    break
                if page_hrefs:
                    seen_page_signatures.add(page_hrefs)

                candidates: list = []
                deep_dive_queue: list = []

                for card in cards:
                    if processed_cards >= max_items:
                        break
                    processed_cards += 1
                    try:
                        brand = None
                        if rule.brand_css:
                            brand_el, _ = self._try_selectors(card, rule.brand_css)
                            brand = self.extract_clean_text(brand_el)

                        title_el, _ = self._try_selectors(card, rule.title_css)
                        title = self.extract_clean_text(title_el)
                        if brand and title and title.upper().startswith(brand.upper()):
                            title = title[len(brand):].strip()
                        if not title:
                            continue

                        lower_title = title.lower()
                        if any(b in lower_title for b in PRODUCT_BLACKLIST):
                            continue

                        price_val = Decimal("0.00")
                        is_available = False
                        if rule.price_css:
                            price_el, _ = self._try_selectors(card, rule.price_css)
                            price_text = self.extract_clean_text(price_el)
                            price_val = self.parse_price(price_text)
                            is_available = bool(price_val and price_val > Decimal("0"))

                        # Notino: volume from variant-name; discount price from pink span
                        variant_texts = card.css(
                            "[data-testid='product-tile-variant-name']::text,"
                            "[data-testid='product-card-variant-name']::text"
                        ).getall()
                        if variant_texts:
                            v_text = " ".join(t.strip() for t in variant_texts if t.strip())
                            if v_text and not re.search(
                                r'\d+[.,]?\d*\s*(ml|l|oz)\b', title, re.IGNORECASE
                            ):
                                title = f"{title} {v_text}"
                        discount_text = card.css("span[style*='#dc0069']::text").get()
                        if discount_text:
                            dv = self.parse_price(discount_text)
                            if dv and dv > Decimal("0") and (not price_val or dv < price_val):
                                price_val = dv
                                is_available = True

                        image_url = None
                        if rule.image_css:
                            img_el, _ = self._try_selectors(card, rule.image_css)
                            if img_el:
                                image_url = img_el.css(
                                    "img::attr(src),img::attr(data-src),::attr(src)"
                                ).get()
                                if image_url:
                                    image_url = urljoin(current_url, image_url)

                        link = card.css("a::attr(href)").get() or card.css("*::attr(href)").get()
                        product_url = urljoin(current_url, link) if link else current_url
                        info = listing.get(product_url) or {}
                        if "outofstock" in str(info.get("stockAvailability") or "").lower():
                            is_available = False
                        # An out-of-stock card shows no price, but the listing data still
                        # has the shop's price: keep it instead of saving the product at 0 €.
                        if not price_val or price_val <= 0:
                            listed = (info.get("priceInformation") or {}).get("price")
                            if listed:
                                price_val = self.parse_price(str(listed))

                        perform_deep_dive = rule.use_detail_page
                        if (rule.detail_variant_selector == "SKIP" or rule.domain in self.detail_skip_domains):
                            perform_deep_dive = False
                        elif perform_deep_dive and rule.detail_trigger_text:
                            card_text = card.xpath("string(.)").get().lower()
                            keywords = [k.strip().lower() for k in rule.detail_trigger_text.split(",")]
                            if not any(k in card_text for k in keywords):
                                perform_deep_dive = False
                        # The card says "sākot ar" only when variant prices differ; the
                        # page's listing data knows every variant and promo code —
                        # except on a card linked to one variant (".../p-16357556/"),
                        # whose listing names only that variant.
                        if (not perform_deep_dive and rule.use_detail_page
                                and rule.detail_variant_selector != "SKIP" and rule.domain not in self.detail_skip_domains
                                and (len(info.get("variants") or []) > 1
                                     or (info.get("promotionData") or {}).get("voucherCode")
                                     or re.search(r"/p-\d+/?$", product_url))):
                            perform_deep_dive = True

                        if perform_deep_dive:
                            deep_dive_queue.append({
                                "url": product_url,
                                "title": title,
                                "brand": brand,
                                "image_url": image_url,
                                "catalog_volume": None,
                                "catalog_concentration": None,
                            })
                        else:
                            # A one-size product often has no volume on its card; the
                            # listing data names it ("100 ml").
                            only = info.get("variants") or []
                            if len(only) == 1 and not re.search(r'\d+(?:[.,]\d+)?\s*(ml|g|l)\b', title, re.IGNORECASE):
                                size = (only[0].get("additionalInfo") or "").strip()
                                if re.search(r'\d', size):
                                    title = f"{title} {size}"
                            norm = perfume_normalizer.extract_all(title)
                            listing_variants = self._extract_variants(card, norm["clean_name"])
                            if listing_variants:
                                for v in listing_variants:
                                    self._add_candidate(
                                        candidates, v["title"], v["price"],
                                        v["price"] > 0, product_url, image_url, brand, norm
                                    )
                            else:
                                self._add_candidate(
                                    candidates, title, price_val,
                                    is_available, product_url, image_url, brand, norm
                                )
                    except Exception as e:
                        logger.debug(f"Notino card parse error: {e}")
                        continue

                # --- CLICK NEXT PAGE IMMEDIATELY — before deep dives ---
                # Deep dives take ~60s. If we click AFTER them, React's SPA
                # event handlers may be gone (CF keepalive or React state reset).
                # Click NOW while page is still "fresh", then do deep dives while
                # the browser loads the next page in parallel.
                old_url = page.url
                has_next = False
                if processed_cards < max_items:
                    await _dismiss_cmp()
                    try:
                        target_page = str(page_number + 1)
                        moved = (None if total_pages and page_number >= total_pages
                                 else await self._notino_next_page(page))
                        if moved:
                            has_next = True
                            logger.info(f"✅ Notino: page {target_page} loaded in the same tab")
                        elif moved is None:
                            logger.info(f"⏹️ Notino: no next button after page {page_number} — last page.")
                        # Fallback: open the page URL in a fresh context.
                        elif notino_pagination_fmt:
                            # e.g. /viriesu-smarzas/?f={pageNumber}-{sortOption}-55544-55549
                            next_path = notino_pagination_fmt.replace("{pageNumber}", target_page).replace("{sortOption}", "1")
                            next_url = f"https://www.notino.lv{next_path}"
                            
                            logger.info(f"➡️ Notino: Universal Fetch for {next_url}")
                            from app.core.browser import browser_manager
                            # Use get_page_content to launch a fresh stealth context for the next page,
                            # bypassing all SPA detection and context flag issues!
                            res = await browser_manager.get_page_content(
                                next_url,
                                fast_mode=True,
                                verified_domain=False # Allow CF solver to trigger if needed
                            )
                            if res and res.get("html") and not self._try_selectors(
                                    ScrapySelector(text=res["html"]), rule.container_css)[0]:
                                # A Cloudflare check that outlasted the wait: try once more.
                                logger.warning(f"⚠️ Notino: page {target_page} came back without cards, retrying once")
                                await asyncio.sleep(random.uniform(3.0, 6.0))
                                res = await browser_manager.get_page_content(
                                    next_url, fast_mode=True, verified_domain=False
                                )

                            if res and res.get("html"):
                                current_html_override = res["html"]
                                current_url_override = res["url"]
                                has_next = True
                                logger.info("✅ Notino: Fetch successful. Page 2+ HTML acquired.")
                            else:
                                logger.error("⏹️ Notino: Fetch failed or Turnstile blocked.")
                                has_next = False
                                
                        else:
                            logger.error("⏹️ Notino: No pagination format available.")
                        
                    except Exception as e:
                        logger.info(f"⏹️ Notino: fetch failed on page {target_page}: {e}. Last page.")

                # Deep dives (next page is already loading in background)
                if deep_dive_queue:
                    from urllib.parse import urlparse as _urlparse
                    domain_key = _urlparse(current_url).netloc.replace("www.", "")
                    _dd_cfg = DOMAIN_DEEP_DIVE_CONFIG.get(
                        domain_key, DOMAIN_DEEP_DIVE_CONFIG["_default"]
                    )
                    concurrent_limit = _dd_cfg["concurrent"]

                    def _delay(_cfg=_dd_cfg):
                        return random.uniform(_cfg["delay_min"], _cfg["delay_max"])

                    logger.info(
                        f"🔍 Notino deep dives: {len(deep_dive_queue)} (limit {concurrent_limit})"
                    )
                    semaphore = asyncio.Semaphore(concurrent_limit)

                    async def _process_job(job):
                        async with semaphore:
                            await asyncio.sleep(_delay())
                            details = await self.scrape_product_details(
                                job["url"], rule, session=session, browser_context=None
                            )
                            # A single-volume card already put its volume into the
                            # title ("… vīriešiem 100 ml"); drop it, or every variant
                            # would be read as that volume (normalizer takes the first).
                            base = re.sub(
                                r'\b(?:\d+\s*[x×]\s*)?\d+(?:[.,]\d+)?\s*(ml|l|oz|g)\b'
                                r'(?:\s+(?:refill|uzpilde|without stand|bez statīva)\b)?',
                                '', job["title"], flags=re.IGNORECASE,
                            )
                            base = re.sub(r"\s+", " ", base).strip()
                            out = []
                            for d in details:
                                ft = f"{base} {d['title_suffix']}".strip()
                                out.append({
                                    "url": job["url"],
                                    "image_url": job["image_url"],
                                    "brand": job["brand"],
                                    "title": ft,
                                    "price": d["price"],
                                    "is_available": d["is_available"],
                                    "catalog_concentration": None,
                                    "promo_price": d.get("promo_price"),
                                    "promo_code": d.get("promo_code"),
                                })
                            return out

                    tasks = [_process_job(j) for j in deep_dive_queue]
                    for f in asyncio.as_completed(tasks):
                        res = await f
                        for d in res:
                            norm = perfume_normalizer.extract_all(d["title"])
                            self._add_candidate(
                                candidates, d["title"], d["price"], d["is_available"],
                                d["url"], d["image_url"], d["brand"], norm,
                                promo_price=d.get("promo_price"), promo_code=d.get("promo_code"),
                            )

                # Flush page to DB
                page_saved = await self._flush_candidates(
                    session, candidates, rule, group_id, intent
                )
                final_scraped_items.extend(page_saved)
                candidates.clear()

                if not has_next or processed_cards >= max_items:
                    logger.info(f"🛑 Notino: stopping after page {page_number}.")
                    break

                # URL doesn't change on Notino SPA pagination.
                # We just wait for network idle to ensure the next page has loaded.

                # The wait_for_load_state has been moved up to immediately after click

                await _dismiss_cmp()
                logger.info(f"✅ Notino: now on page {page_number + 1} — {page.url}")
                await asyncio.sleep(random.uniform(0.5, 1.0))

        finally:
            try:
                await page.close()
            except Exception:
                pass
            try:
                await ctx.close()
            except Exception:
                pass

        return final_scraped_items

    async def _scrape_makeup_via_api(
        self,
        session,
        rule,
        start_url: str,
        max_items: int,
        group_id,
        intent,
        site_name_ui,
        start_offset: int = 0,
    ) -> list:
        """Scrape makeup.lv via its REST API, bypassing SSR.

        SSR hydration on makeup.lv always returns page-1 data regardless of
        URL — pagination happens client-side after React mounts and calls
        /shop/v1/categories/{id}/products/?offset=N. We hit that endpoint
        directly. One browser context is needed for AWS WAF cookies; after
        that everything is plain HTTP.
        """
        import json
        from app.core.browser import browser_manager
        from app.services.normalizer import perfume_normalizer, detect_card_type, is_non_perfume_title

        cat_match = re.search(r'/categorys/(\d+)', start_url)
        if not cat_match:
            logger.error(f"makeup: cannot extract category id from {start_url}")
            return []
        cat_id = cat_match.group(1)

        ctx = await browser_manager.get_context()
        final_scraped_items: list = []

        try:
            # Warm-up: fetch a real page so AWS WAF issues cookies on this context.
            page = await ctx.new_page()
            try:
                await page.goto(start_url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(3)
            finally:
                await page.close()

            offset = start_offset
            page_size = 36
            page_number = 1 + start_offset // page_size
            total_count: int | None = None

            from app.services.ui import get_dashboard
            db = get_dashboard()

            while True:
                api_url = f"https://makeup.lv/shop/v1/categories/{cat_id}/products/?offset={offset}"
                logger.info(f"🎯 Makeup API: page {page_number} (offset={offset})")
                if db and site_name_ui:
                    db.update_status(site_name_ui, f"Loading Page {page_number}")

                try:
                    resp = await ctx.request.get(api_url, timeout=30000)
                except Exception as e:
                    logger.error(f"makeup api fetch failed at offset={offset}: {e}")
                    break

                if resp.status != 200:
                    logger.error(f"makeup api returned {resp.status} at offset={offset}")
                    break

                try:
                    data = json.loads(await resp.text())
                except Exception as e:
                    logger.error(f"makeup api json parse failed: {e}")
                    break

                if total_count is None:
                    total_count = int(data.get("totalCount") or data.get("total") or 0)
                    page_size = int(data.get("perPage") or page_size)
                    logger.success(f"🎯 Makeup catalog: {total_count} total products, perPage={page_size}")

                products_raw = data.get("products", []) or []
                products = [p for p in products_raw if p.get("type") == "product"]
                logger.info(f"🎯 Page {page_number}: {len(products)} products (filtered from {len(products_raw)})")

                if not products:
                    logger.info(f"makeup: empty page at offset={offset}, stopping")
                    break

                candidates: list = []
                for p in products:
                    base_title = (p.get("title") or "").strip()
                    if any(b in base_title.lower() for b in PRODUCT_BLACKLIST):
                        continue
                    brand = ((p.get("brand") or {}).get("title") or "").strip()
                    link = (p.get("link") or "").strip()
                    full_link = f"https://makeup.lv{link}" if link.startswith("/") else (link or start_url)

                    image_url = None
                    media = p.get("media")
                    if isinstance(media, dict):
                        sizes = media.get("sizes") or {}
                        image_url = (sizes.get("lg") or {}).get("url") or media.get("url")
                    elif isinstance(media, list) and media and isinstance(media[0], dict):
                        sizes = media[0].get("sizes") or {}
                        image_url = (sizes.get("lg") or {}).get("url") or media[0].get("url")

                    sub_title = (p.get("subTitle") or "").strip()
                    is_set = bool(p.get("isGift")) or detect_card_type(base_title, sub_title) == "gift_set"
                    # makeup.lv names the product type in the subtitle
                    # ("Dezodorants-aerosols"); the title alone looks like a perfume.
                    if not is_set and (
                        any(b in sub_title.lower() for b in PRODUCT_BLACKLIST) or is_non_perfume_title(sub_title)
                    ):
                        continue

                    base_norm = perfume_normalizer.extract_all(base_title)
                    if sub_title and not base_norm.get("concentration"):
                        sub_conc = perfume_normalizer.extract_all(sub_title).get("concentration")
                        if sub_conc:
                            base_norm["concentration"] = sub_conc

                    in_stock = bool(p.get("inStock"))
                    price_obj = p.get("price") or {}
                    current = price_obj.get("current")
                    # None = the card shows no price (out of stock); never store it as 0 €
                    fallback_price = Decimal(str(current)).quantize(Decimal("0.01")) if current else None

                    # Gift sets: makeup.lv marks them in the subtitle
                    # ("Komplekts (edp/100ml + edp/mini/10ml)"), not the title.
                    # One entry per set; the composition stays in the title.
                    if is_set:
                        self._add_candidate(
                            candidates, f"{base_title} {sub_title}".strip(), fallback_price, in_stock,
                            full_link, image_url, brand, base_norm, card_type="gift_set",
                        )
                        continue

                    not_available = {
                        str(x.get("id")) if isinstance(x, dict) else str(x)
                        for x in (p.get("notAvailableVariants") or [])
                    }
                    variants_data = ((p.get("analytics") or {}).get("variantsData")) or {}
                    if isinstance(variants_data, dict) and variants_data:
                        first = len(candidates)
                        for _vid, info in variants_data.items():
                            if not isinstance(info, dict):
                                continue
                            vol = (info.get("value") or "").strip()
                            v_price = Decimal(str(info.get("price") or 0)).quantize(Decimal("0.01"))
                            full_title = f"{base_title} {vol}".strip()
                            self._add_candidate(
                                candidates, full_title, v_price if v_price > 0 else None,
                                in_stock and v_price > 0 and str(_vid) not in not_available,
                                full_link, image_url, brand, base_norm,
                            )
                        # A volume the page no longer lists is gone from the shop:
                        # mark the stored row unavailable instead of leaving it
                        # "in stock" at its last price.
                        listed = {c["volume"] for c in candidates[first:]}
                        gone = (await session.execute(
                            select(Product).where(
                                Product.url == full_link,
                                Product.card_type == "perfume",
                                Product.is_available.is_(True),
                            )
                        )).scalars().all()
                        for old in gone:
                            if old.volume in listed:
                                continue
                            candidates.append({
                                "url": old.url, "image_url": old.image_url, "brand": old.brand,
                                "volume": old.volume, "concentration": old.concentration,
                                "title": old.title, "price": None, "is_available": False,
                                "card_type": "perfume", "promo_price": None, "promo_code": None,
                            })
                    elif not in_stock:
                        # Out-of-stock cards list no volumes and no price. Mark the
                        # volumes already known for this product page unavailable
                        # instead of inventing a volume-less row priced 0 €.
                        known_volumes = set((await session.execute(
                            select(Product.volume).where(Product.url == full_link)
                        )).scalars().all()) or {None}
                        for vol in known_volumes:
                            self._add_candidate(
                                candidates, f"{base_title} {vol}" if vol else base_title, None, False,
                                full_link, image_url, brand, base_norm,
                            )
                    else:
                        self._add_candidate(
                            candidates, base_title, fallback_price, in_stock,
                            full_link, image_url, brand, base_norm,
                        )

                if candidates:
                    saved = await self._flush_candidates(session, candidates, rule, group_id, intent)
                    final_scraped_items.extend(saved)

                # Checkpoint
                rule.last_page_url = api_url
                rule.items_scraped_current_run = len(final_scraped_items)
                session.add(rule)
                await session.commit()

                # Stop conditions
                if len(final_scraped_items) >= max_items:
                    logger.info(f"🛑 makeup: reached max_items ({max_items})")
                    break
                if total_count and offset + page_size >= total_count:
                    logger.success(f"🏁 makeup: reached end of catalog ({total_count} products)")
                    break

                offset += page_size
                page_number += 1
                await asyncio.sleep(random.uniform(0.4, 1.0))

            # Quality control + checkpoint reset (mirrors main scrape_catalog tail)
            from datetime import datetime as _dt
            report = self.validate_dataset(final_scraped_items)
            rule.health_score = report["score"]
            rule.last_page_url = None
            rule.items_scraped_current_run = 0
            if report["is_healthy"]:
                rule.last_success = _dt.utcnow()
                rule.success_count += 1
                rule.last_error = None
                logger.success(f"💎 Data quality confirmed: {report['score']} ({len(final_scraped_items)} items)")
                await self.learn_from_success(session, rule)
            else:
                rule.failure_count += 1
                rule.last_error = report.get("error", "Unknown error")
                logger.warning(f"💊 Low data quality: {report['score']} | Error: {rule.last_error}")
            session.add(rule)
            await session.commit()
        finally:
            try:
                await ctx.close()
            except Exception:
                pass

        return final_scraped_items

    def _extract_makeup_variants_from_json(self, html: str, current_url: str) -> list[dict]:
        import json
        import re
        from decimal import Decimal
        from urllib.parse import urljoin
        
        results = []
        match = re.search(r'__staticQueryClientHydrationData\s*=\s*JSON\.parse\((.*?)\);', html)
        if not match:
            return results
            
        try:
            json_str_literal = match.group(1)
            actual_json_str = json.loads(json_str_literal)
            data = json.loads(actual_json_str)
            
            queries = data.get('queries', [])
            for q in queries:
                q_data = q.get('state', {}).get('data', {})
                items = []
                if isinstance(q_data, dict):
                    items = q_data.get('items', [])
                elif isinstance(q_data, list):
                    if len(q_data) > 0 and isinstance(q_data[0], dict) and 'items' in q_data[0]:
                        items = q_data[0].get('items', [])
                
                if not items and isinstance(q_data, list):
                    items = q_data
                
                search_items = []
                if isinstance(items, dict):
                    for v in items.values():
                        if isinstance(v, list):
                            search_items.extend(v)
                else:
                    search_items = items
                    
                if isinstance(q_data, dict) and 'pages' in q_data:
                    for p in q_data.get('pages', []):
                        if 'products' in p:
                            search_items.extend(p['products'])
                            
                for item in search_items:
                    if not isinstance(item, dict): continue
                    if 'analytics' not in item or 'title' not in item: continue
                    
                    base_title = item.get('title', '')
                    brand = item.get('brand', {}).get('title', '') if isinstance(item.get('brand'), dict) else ''
                    link = item.get('link', '')
                    full_link = urljoin(current_url, link) if link else current_url
                    
                    image_url = None
                    media = item.get('media', [])
                    if isinstance(media, list) and media:
                        if isinstance(media[0], dict):
                            sizes = media[0].get('sizes', {})
                            image_url = sizes.get('lg', {}).get('url') or media[0].get('url')
                    elif isinstance(media, dict):
                        image_url = media.get('url')
                        
                    sub_title = item.get('subTitle', '') or ''

                    variants_data = item.get('analytics', {}).get('variantsData', {})
                    if variants_data and isinstance(variants_data, dict):
                        for v_id, info in variants_data.items():
                            vol = info.get('value', '')
                            price_val = Decimal(str(info.get('price', 0))).quantize(Decimal("0.01"))

                            results.append({
                                "base_title": base_title,
                                "price": price_val,
                                "is_available": price_val > 0,
                                "url": full_link,
                                "image_url": image_url,
                                "brand": brand,
                                "volume": vol,
                                "sub_title": sub_title,
                            })
                    else:
                        price_val = Decimal(str(item.get('analytics', {}).get('price', 0))).quantize(Decimal("0.01"))
                        if price_val > 0:
                            results.append({
                                "base_title": base_title,
                                "price": price_val,
                                "is_available": True,
                                "url": full_link,
                                "image_url": image_url,
                                "brand": brand,
                                "volume": item.get('analytics', {}).get('variant', ''),
                                "sub_title": sub_title,
                            })
                            
        except Exception as e:
            logger.error(f"Failed parsing makeup JSON variants: {e}")
            
        return results

    def _extract_220_from_widget_data(self, html: str) -> list[dict]:
        """
        220.lv is a SPA (Pigu platform). Each product card has a `widget-data`
        attribute containing a full JSON object with clean decimal prices.

        A card shows either one public price, or a "220.lv PLUS" loyalty price
        (span.h-price--loyalty, members only) next to the public price. With a
        loyalty price, widget `price` is the loyalty price and `regular_price`
        the public one. The public price is the product's price; the loyalty
        price is kept as promo_price / promo_code "220.lv PLUS".
        """
        import json
        from parsel import Selector

        results = []
        sel = Selector(text=html)

        for card in sel.css('div.c-product-card[widget-data]'):
            try:
                data = json.loads(card.attrib['widget-data'])
                dl = data.get('dataLayerItem', {})

                title     = data.get('title', '').strip()
                url       = data.get('url', '')
                # photoUrl is the 21×46 px "_xsmall" thumbnail; "_reference" is the
                # size the shop's own product page shows (about 480×1024).
                image_url = re.sub(r'_(?:xsmall|small|medium|large|big)\.(jpe?g|png|webp)$', r'_reference.\1',
                                   data.get('photoUrl', ''))
                brand     = dl.get('item_brand', '')
                status    = dl.get('item_status', 'active')

                # regular_price = standard retail price (non-loyalty)
                # price         = loyalty/PLUS member price (requires subscription)
                # 220.lv widget-data is inconsistent across deploys: sometimes int cents (4499),
                # sometimes float cents (2389.00), rarely float euros (44.99). Type-based detection
                # fails on float-cents. The prices shown on the card (aria-label "742,20 €") decide
                # the scale; without them, anything > 500 is taken as cents.
                shown = []
                for lbl in card.css('.c-product-card__prices .c-price::attr(aria-label)').getall():
                    m = re.search(r'\d+(?:[.,]\d+)?', re.sub(r'\s+', '', lbl))
                    if m:
                        shown.append(Decimal(m.group(0).replace(',', '.')))

                def _norm_220_price(raw) -> Decimal:
                    if raw is None:
                        return Decimal('0.00')
                    v = Decimal(str(raw))
                    if shown:
                        if not any(abs(v - s) < Decimal('0.02') for s in shown) and \
                                any(abs(v / 100 - s) < Decimal('0.02') for s in shown):
                            v = v / 100
                    elif v > Decimal('500'):
                        v = v / 100
                    return v.quantize(Decimal('0.01'))

                regular_price = _norm_220_price(dl.get('regular_price'))
                sell_price    = _norm_220_price(dl.get('price'))

                promo_price = None
                if card.css('.h-price--loyalty') and regular_price > 0:
                    final_price = regular_price
                    if 0 < sell_price < regular_price:
                        promo_price = sell_price
                else:
                    final_price = sell_price if sell_price > 0 else regular_price
                is_available = status == 'active' and final_price > 0

                if title and final_price > 0:
                    results.append({
                        'base_title': title,
                        'price':      final_price,
                        'is_available': is_available,
                        'url':        url,
                        'image_url':  image_url,
                        'brand':      brand,
                        'volume':     '',   # volume embedded in title for this site
                        'promo_price': promo_price,
                        'promo_code':  '220.lv PLUS' if promo_price else None,
                    })
            except Exception as e:
                logger.debug(f'220.lv widget-data parse error: {e}')

        return results

    def _extract_1a_cards(self, html: str, base_url: str) -> list[dict]:
        """1a.lv catalog cards, rendered by LupaSearch (selectors verified on the
        live page by Ervin, 2026-10-08).

        A card shows the regular price and, for most products, a lower
        "SMART NET" loyalty-card price. The regular price is the product's
        price; the SMART NET price is kept as promo_price / promo_code
        "SMART NET". Brand, concentration and volume come from the card's
        attribute list (Zīmols / Koncentrācija / Tilpums).
        """
        from urllib.parse import urljoin, urlsplit, urlunsplit

        def _price(text: str | None) -> Decimal | None:
            if not text:
                return None
            m = re.search(r'\d[\d\s ]*(?:[.,]\d+)?', text)
            if not m:
                return None
            value = self.parse_price(m.group(0))
            return value if value > 0 else None

        results = []
        sel = Selector(text=html)
        for card in sel.css('div.lupa-search-result-product-card'):
            try:
                link = card.css('a.lupa-title-link')
                title = " ".join(link.xpath('string(.)').get(default="").split()) \
                    or (card.css('.lupa-search-results-product-title::attr(title)').get() or "").strip()
                href = link.attrib.get('href') if link else \
                    card.css('a.lupa-search-result-product-image-section::attr(href)').get()
                if not title or not href:
                    continue
                # Drop the LupaSearch tracking query (?mtd=search-popup&...&src=lupasearch)
                parts = urlsplit(urljoin(base_url, href))
                url = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

                attrs = {}
                for li in card.css('li.catalog-taxons-product-key-attribute-list__item'):
                    value = " ".join(li.css('.catalog-taxons-product-key-attribute-list__item-value').xpath('string(.)').get(default="").split())
                    label = " ".join(" ".join(li.xpath('./text()').getall()).split()).rstrip(':').strip().lower()
                    if label and value:
                        attrs[label] = value

                regular = _price(card.css('.catalog-taxons-product__price .catalog-taxons-product-price__item-price').xpath('string(.)').get())
                smart = _price(card.css('.special-price .catalog-taxons-product-price__price-number').xpath('string(.)').get())
                price = regular or smart
                if not price:
                    continue
                promo_price = smart if regular and smart and smart < regular else None

                # Every card element carries instock="true|false"; a sold-out
                # card also fills .lupa-element-group-soldout ("Izpārdots").
                in_stock_flags = card.css('[instock]::attr(instock)').getall()
                sold_out = bool(card.css('.lupa-element-group-soldout').xpath('normalize-space(string(.))').get())
                is_available = (not in_stock_flags or "true" in in_stock_flags) and not sold_out

                results.append({
                    'base_title': title,
                    'price': price,
                    'is_available': is_available,
                    'url': url,
                    'image_url': card.css('img.lupa-search-results-image::attr(src)').get() or "",
                    'brand': attrs.get('zīmols', ''),
                    'concentration': attrs.get('koncentrācija', ''),
                    'volume': attrs.get('tilpums', ''),
                    'promo_price': promo_price,
                    'promo_code': 'SMART NET' if promo_price else None,
                })
            except Exception as e:
                logger.debug(f'1a.lv card parse error: {e}')
        return results

    def _extract_douglas_catalog_volume(self, card: Selector) -> str | None:
        """Read single-variant volume (e.g. '50ml') from a Douglas catalog card's
        data-tealium-info attribute. Needed because the product detail page
        returns an EMPTY variant name for single-size products, losing volume."""
        import json
        import html as html_lib
        ti_raw = card.css('a::attr(data-tealium-info)').get('') or ''
        if not ti_raw:
            return None
        try:
            d = json.loads(ti_raw)
            cv = ((d.get('primary_product_variant_name') or [''])[0] or '').strip()
            return html_lib.unescape(cv) if cv else None
        except Exception:
            return None

    def _douglas_card_has_variants(self, card: Selector) -> bool:
        """True when a Douglas catalog card's data-tealium-info says the product
        comes in several variants (volumes)."""
        import json
        ti_raw = card.css('a::attr(data-tealium-info)').get('') or ''
        try:
            d = json.loads(ti_raw) if ti_raw else {}
        except Exception:
            return False
        return ((d.get('primary_product_variants') or [''])[0] or '').lower() == 'yes'

    @staticmethod
    def _notino_listing_data(data, base_url: str) -> dict:
        """The product list (variants, stock, promo code of every card) inside
        notino.lv listing JSON. Returns {product url: product}."""
        def find(o):
            if isinstance(o, dict):
                prods = o.get("products")
                if isinstance(prods, list) and prods and isinstance(prods[0], dict) and "productCode" in prods[0]:
                    return prods
                o = list(o.values())
            if isinstance(o, list):
                for v in o:
                    found = find(v)
                    if found:
                        return found
            return None

        found = find(data) or []
        return {urljoin(base_url, p.get("url") or ""): p for p in found}

    def _notino_listing(self, page_html: str, base_url: str) -> dict:
        """notino.lv embeds the first catalog page's product list as JSON."""
        import json
        for raw in Selector(text=page_html).css("script[type='application/json']::text").getall():
            if '"productCode"' not in raw or '"variants"' not in raw:
                continue
            try:
                listing = self._notino_listing_data(json.loads(raw), base_url)
            except Exception:
                continue
            if listing:
                return listing
        return {}

    @staticmethod
    async def _notino_next_page(page) -> bool | None:
        """Go to the next catalog page inside the same tab, the way a visitor
        does. The "next" button loads the list through Notino's navigation API
        (POST /api/navigation/navigation/…) — no new page load, so Cloudflare
        doesn't check it again. True when the next page is shown, None when
        there is no next button (last page), False when the click changed nothing."""
        cards = page.locator("[data-testid='product-container'] a")
        first = await cards.first.get_attribute("href")
        # The last visible pager button is "next" (the caller stops at the last
        # page, where it would be "previous"); the .nextPage class is a fallback.
        found = False
        for selector in ("[data-testid='page-button-wrapper']:visible",
                         "[data-testid='page-button-wrapper'].nextPage:visible"):
            buttons = page.locator(selector)
            if not await buttons.count():
                continue
            found = True
            button = buttons.last
            await button.scroll_into_view_if_needed(timeout=5000)
            await button.click(timeout=5000)
            for _ in range(30):  # up to 15 s for the new cards
                await asyncio.sleep(0.5)
                try:
                    if await cards.first.get_attribute("href", timeout=1000) != first:
                        await asyncio.sleep(1.0)  # let the rest of the grid render
                        return True
                except Exception:
                    continue
        return False if found else None

    async def scrape_catalog(self, session, start_url: str, initial_html: str = None, max_items: int = 100, group_id: Optional[int] = None, intent: dict = None, enable_price_filter: bool = True, site_name_ui: str = None):
        domain = urlparse(start_url).netloc.replace("www.", "")
        self.detail_skip_domains.discard(domain)  # a new run tries deep dives again
        
        statement = select(ScrapingRule).where(ScrapingRule.domain == domain)
        result = await session.execute(statement)
        rule = result.scalar_one_or_none()
        if not rule: return []

        # notino.lv: Cloudflare blocks any new-page navigation to the same URL.
        # Must use a single persistent Playwright page that clicks the nextPage
        # chevron in-place — CF is never re-challenged within the same session.
        if "notino.lv" in domain:
            return await self._scrape_notino_catalog(
                session, rule, start_url, max_items, group_id, intent, site_name_ui
            )

        # makeup.lv: SSR hydration is static (always page-1 regardless of URL).
        # The React client paginates via REST API. Scrape that directly — much
        # faster (HTTP GET vs full browser render) and gets the real catalog.
        if "makeup.lv" in domain or "makeup." in domain:
            return await self._scrape_makeup_via_api(
                session, rule, start_url, max_items, group_id, intent, site_name_ui
            )

        candidates = []
        deep_dive_queue = []  # Per-page queue for concurrent deep dives
        html = initial_html
        current_url = start_url
        page_number = 1
        processed_cards = 0
        next_click_selector = None # For JS Pagination
        next_page_link = None # Initialize for reset logic visibility
        seen_page_signatures: set = set()  # Loop detection: frozenset of card hrefs per page
        final_scraped_items: list = []  # Accumulated across all pages (incremental saves)

        # --- PERSISTENT BROWSER CONTEXT ---
        # One context for the whole catalog scrape: cookies/session persist across
        # pages so JS challenges (Cloudflare/CDN) only need to be solved once.
        # Without this, every page=N fetch is a fresh visitor — sites like makeup.lv
        # respond to the cold session with a stub of page 1 instead of the real offset.
        from app.core.browser import browser_manager
        persistent_context = await browser_manager.get_context()

        # --- RESUME LOGIC (Checkpoint) ---
        if rule.last_page_url and rule.last_page_url.startswith(start_url.split('?')[0]):
            logger.info(f"🔄 Resuming from checkpoint: {rule.last_page_url}")
            current_url = rule.last_page_url
            processed_cards = rule.items_scraped_current_run
            html = None # Force fresh fetch
        
        from app.services.ui import get_dashboard
        db = get_dashboard()

        ai_retry_attempted = False

        while processed_cards < max_items:
            # Check if we have a valid URL or a pending click
            if not current_url and not next_click_selector:
                break

            if db and site_name_ui:
                db.update_status(site_name_ui, f"Loading Page {page_number}")
            
            # --- FETCH PAGE ---
            # Reuse the persistent context so cookies/anti-bot challenge state survive
            # across pages. Required for sites like makeup.lv where a fresh visitor
            # always gets the page-1 stub regardless of the requested URL.
            page_response = await self.scrape_page(
                current_url,
                rule=rule,
                browser_context=persistent_context,
                click_selector=next_click_selector,
            )
            
            if not page_response or not page_response.get("html"):
                logger.warning(f"⚠️ Page {page_number} failed to load.")
                break 

            html = page_response["html"]
            # Important: Update URL because a click might have changed it!
            if page_response.get("url"):
                current_url = page_response["url"]
            
            # Reset click selector for next iteration
            next_click_selector = None 

            sel = Selector(text=html)
            rule_updated = False
            # Set by any successful JSON-injection path; suppresses the
            # "cards not found" fallback/error that would otherwise break
            # pagination when we intentionally empty `cards` after injection.
            injection_ok = False
            # When JSON-injection populates candidates instead of DOM cards,
            # cards=[] makes the standard loop-detection signature empty.
            # Branches that use injection assign the URL set here so the
            # signature check below can still detect a repeated page.
            injection_signature: frozenset = frozenset()

            # --- 220.LV WIDGET-DATA JSON INJECTION (SPA / Pigu platform) ---
            if "220.lv" in domain:
                items_220 = self._extract_220_from_widget_data(html)
                if items_220:
                    logger.success(f"🏪 220.lv widget-data yielded {len(items_220)} products!")
                    from app.services.normalizer import perfume_normalizer, detect_card_type
                    unique_products_220 = set()
                    for mi in items_220:
                        lower_title = mi['base_title'].lower()
                        if any(b in lower_title for b in PRODUCT_BLACKLIST): continue
                        # Ervin (2026-10-02): gift sets from 220.lv are not stored.
                        if detect_card_type(mi['base_title']) == "gift_set": continue
                        unique_products_220.add(mi['url'])
                        base_norm = perfume_normalizer.extract_all(mi['base_title'])
                        full_title = f"{mi['base_title']} {mi['volume']}".strip()
                        self._add_candidate(candidates, full_title, mi['price'], mi['is_available'], mi['url'], mi['image_url'], mi['brand'], base_norm,
                                            promo_price=mi['promo_price'], promo_code=mi['promo_code'])
                    processed_cards += len(unique_products_220)
                    cards = []  # Skip standard DOM loop
                    injection_ok = True
                    injection_signature = frozenset(unique_products_220)
                else:
                    logger.warning("⚠️ 220.lv widget-data yielded 0 items — falling back to DOM selectors")
                    cards, winner = self._try_selectors(sel, rule.container_css)

            # --- 1A.LV LUPASEARCH CARDS ---
            elif "1a.lv" in domain:
                items_1a = self._extract_1a_cards(html, current_url)
                if items_1a:
                    logger.success(f"🛒 1a.lv cards yielded {len(items_1a)} products!")
                    from app.services.normalizer import perfume_normalizer
                    unique_products_1a = set()
                    for mi in items_1a:
                        if any(b in mi['base_title'].lower() for b in PRODUCT_BLACKLIST): continue
                        unique_products_1a.add(mi['url'])
                        base_norm = perfume_normalizer.extract_all(mi['base_title'], explicit_brand=mi['brand'])
                        # The card's attribute list ("Koncentrācija", "Tilpums") is
                        # more reliable than the title.
                        if mi['concentration']:
                            attr_conc = perfume_normalizer.extract_all(mi['concentration']).get("concentration")
                            if attr_conc:
                                base_norm["concentration"] = attr_conc
                        if mi['volume']:
                            base_norm["volume"] = perfume_normalizer.extract_volume(mi['volume']) or base_norm.get("volume")
                        full_title = mi['base_title']
                        if mi['volume'] and not perfume_normalizer.extract_volume(full_title):
                            full_title = f"{full_title} {mi['volume']}"
                        self._add_candidate(candidates, full_title, mi['price'], mi['is_available'], mi['url'], mi['image_url'], mi['brand'], base_norm,
                                            promo_price=mi['promo_price'], promo_code=mi['promo_code'])
                    processed_cards += len(unique_products_1a)
                    cards = []  # Skip standard DOM loop
                    injection_ok = True
                    injection_signature = frozenset(unique_products_1a)
                else:
                    logger.warning("⚠️ 1a.lv: no LupaSearch cards found — falling back to DOM selectors")
                    cards, winner = self._try_selectors(sel, rule.container_css)

            # --- MAKEUP.LV JSON DATA INJECTION ---
            elif "makeup.lv" in domain or "makeup." in domain:
                makeup_items = self._extract_makeup_variants_from_json(html, current_url)
                if makeup_items:
                    logger.success(f"🎯 Makeup JSON parsing yielded {len(makeup_items)} variant entries!")
                    from app.services.normalizer import perfume_normalizer

                    unique_products = set()

                    for mi in makeup_items:
                        lower_title = mi['base_title'].lower()
                        if any(b in lower_title for b in PRODUCT_BLACKLIST): continue

                        unique_products.add(mi['url'])

                        base_norm = perfume_normalizer.extract_all(mi["base_title"])
                        sub = mi.get("sub_title")
                        if sub and not base_norm.get("concentration"):
                            sub_conc = perfume_normalizer.extract_all(sub).get("concentration")
                            if sub_conc:
                                base_norm["concentration"] = sub_conc
                        full_title = f"{mi['base_title']} {mi['volume']}".strip()
                        self._add_candidate(candidates, full_title, mi["price"], mi["is_available"], mi["url"], mi["image_url"], mi["brand"], base_norm)

                    processed_cards += len(unique_products)
                    cards = [] # Emulate no DOM cards to skip the standard loop
                    injection_ok = True
                    injection_signature = frozenset(unique_products)
                else:
                   cards, winner = self._try_selectors(sel, rule.container_css)
            else:
                cards, winner = self._try_selectors(sel, rule.container_css)

            # 1. CARDS
            if not cards and not injection_ok:
                 # Universal fallback for generic store structures
                 cards, winner = self._try_selectors(sel, FALLBACK_CONTAINER_CSS)
                 if cards and winner:
                     logger.warning(f"🔧 [Auto-Fix] Switching container for {domain}: {rule.container_css} -> {winner}")
                     rule.container_css = winner
                     rule_updated = True

            if not cards and not injection_ok:
                 logger.error(f"❌ Cards not found ({rule.container_css})")
                 
                 if not ai_retry_attempted:
                     logger.warning(f"🤖 Triggering AI Self-Healing for {domain}...")
                     ai_retry_attempted = True
                     
                     if db and site_name_ui:
                         db.update_status(site_name_ui, "AI Healing DOM...", progress=0)
                     
                     from app.services.ai_generator import ai_generator
                     hint = f"Elements matching previous container_css '{rule.container_css}' were NOT found. Find the correct repeating product container."
                     
                     new_rule = await ai_generator.get_or_create_rule(session, current_url, html, force_refresh=True, error_hint=hint)
                     if new_rule:
                         logger.success(f"🤖 AI regenerated rule. Retrying card extraction...")
                         rule = new_rule
                         cards, winner = self._try_selectors(sel, rule.container_css)
                         if not cards:
                             logger.error("❌ AI regenerated rule also failed. Skipping page.")
                             break
                     else:
                         logger.error("❌ AI failed to regenerate rule. Skipping page.")
                         break
                 else:
                     logger.error(f"❌ Cards not found ({rule.container_css}), and AI retry already attempted. Giving up.")
                     break
                 
            logger.info(f"{rule.emoji} [Page {page_number}] Cards: {len(cards)}")

            # --- LOOP DETECTION (JS pagination guard) ---
            # Notino and similar SPAs keep the "next page" button visible even on the last
            # page. When clicked it returns identical content. Detect by fingerprinting the
            # set of card hrefs — if we've seen this exact page before, we've looped.
            # When JSON-injection populated candidates (220.lv / makeup), use its URL set.
            if cards:
                page_hrefs = frozenset(
                    card.css("a::attr(href)").get() or ""
                    for card in cards
                ) - {""}  # drop empty strings
            else:
                page_hrefs = injection_signature
            if page_hrefs and page_hrefs in seen_page_signatures:
                logger.info(f"🔁 Loop detected on page {page_number} — same card set already scraped. Stopping pagination.")
                # Douglas repeats its last page instead of ending: that is the end of
                # the catalog, so the next run must start from page 1, not resume here.
                rule.last_page_url = None
                rule.items_scraped_current_run = 0
                session.add(rule)
                await session.commit()
                break
            if page_hrefs:
                seen_page_signatures.add(page_hrefs)

            try:
                for card in cards:
                    if processed_cards >= max_items: break
                    processed_cards += 1
                    try:
                        # 2.5 BRAND — extract first so we can clean it from title
                        brand = None
                        if rule.brand_css:
                            brand_el, _ = self._try_selectors(card, rule.brand_css)
                            brand = self.extract_clean_text(brand_el)

                        # 2.6 CONCENTRATION — optional DOM source (Douglas/Makeup etc.).
                        # Text is in site-native language (e.g. "Tualetes ūdens"),
                        # CONC_MAP translates it to EDT/EDP/EDC inside the normalizer.
                        catalog_concentration = None
                        conc_text = ""
                        if rule.concentration_css:
                            conc_el, _ = self._try_selectors(card, rule.concentration_css)
                            conc_text = self.extract_clean_text(conc_el)
                            if conc_text:
                                from app.services.normalizer import perfume_normalizer as _pn
                                catalog_concentration = _pn.extract_all(conc_text).get("concentration")

                        # 2. TITLE — strip brand prefix if it bleeds in (e.g. Douglas.lv nests .brand_caps inside .name)
                        title_el, winner = self._try_selectors(card, rule.title_css)
                        title = self.extract_clean_text(title_el)
                        if brand and title and title.upper().startswith(brand.upper()):
                            title = title[len(brand):].strip()
                        if not title:
                            title_el, winner = self._try_selectors(card, FALLBACK_TITLE_CSS)
                            title = self.extract_clean_text(title_el)
                            if brand and title and title.upper().startswith(brand.upper()):
                                title = title[len(brand):].strip()
                            if title and winner:
                                rule.title_css = winner
                                rule_updated = True
                        
                        if not title: continue

                        # Douglas prints some line names in the type line instead of a
                        # type ("BLEU DE CHANEL" + "L'EXCLUSIF"): the name belongs to
                        # the title, otherwise the perfume joins the wrong group.
                        from app.services.normalizer import line_name_concentration as _line_name_concentration
                        line_conc = _line_name_concentration(conc_text)
                        if line_conc:
                            if conc_text.lower() not in title.lower():
                                title = f"{title} {conc_text}"
                            catalog_concentration = line_conc

                        # Douglas names a set in the type line under the title
                        # ("Uzpildes komplekts 3 × 20 ml – Parfimērijas ūdens").
                        from app.services.normalizer import detect_card_type as _detect_card_type
                        card_kind = "gift_set" if _detect_card_type(title, conc_text) == "gift_set" else None

                        # --- HARD FILTER (BLACKLIST) ---
                        # We drop non-perfume items entirely here so they never reach the DB or trigger Deep Dives
                        lower_title = title.lower()
                        if any(b in lower_title for b in PRODUCT_BLACKLIST):
                            logger.debug(f"🗑️ Skipping noisy item matching blacklist: {title}")
                            continue

                        # 3. PRICE (Listing)
                        price_val = Decimal("0.00")
                        is_available = False
                        if rule.price_css:
                            price_el, winner = self._try_selectors(card, rule.price_css)
                            price_text = self.extract_clean_text(price_el)
                            price_val = self.parse_price(price_text)
                            is_available = True if price_val and price_val > Decimal("0") else False

                        # === NOTINO-specific: enrich single-variant cards (no deep dive needed) ===
                        # Notino catalog cards expose volume+concentration via product-(tile|card)-variant-name
                        # and discount price via a pink-colored span (#dc0069). Extracting both lets us
                        # skip deep dive for single-variant products (those without "sākot ar" trigger).
                        if "notino.lv" in current_url.lower():
                            variant_texts = card.css(
                                "[data-testid='product-tile-variant-name']::text, "
                                "[data-testid='product-card-variant-name']::text"
                            ).getall()
                            if variant_texts:
                                v_text = " ".join(t.strip() for t in variant_texts if t.strip())
                                if v_text and not re.search(r'\d+[.,]?\d*\s*(ml|l|oz)\b', title, re.IGNORECASE):
                                    title = f"{title} {v_text}"

                            # Prefer discount price (rendered in Notino brand pink #dc0069) over regular
                            discount_text = card.css("span[style*='#dc0069']::text").get()
                            if discount_text:
                                discount_val = self.parse_price(discount_text)
                                if discount_val and discount_val > Decimal("0"):
                                    if not price_val or discount_val < price_val:
                                        price_val = discount_val
                                        is_available = True

                        # 4. IMAGE
                        image_url = None
                        if rule.image_css:
                            img_el, _ = self._try_selectors(card, rule.image_css)
                            if img_el:
                                image_url = img_el.css("img::attr(src), img::attr(data-src), ::attr(src)").get()
                                if image_url: image_url = urljoin(current_url, image_url)

                        # 5. URL
                        product_url = current_url
                        link_node = card.css("a::attr(href)").get()
                        if not link_node: link_node = card.css("*::attr(href)").get()
                        if link_node: product_url = urljoin(current_url, link_node)

                        perform_deep_dive = rule.use_detail_page
                        # --- CRITICAL: Check if Deep Dive was disabled mid-run by self-healing ---
                        if (rule.detail_variant_selector == "SKIP" or rule.domain in self.detail_skip_domains):
                            perform_deep_dive = False
                        elif perform_deep_dive and rule.detail_trigger_text:
                            card_text = card.xpath('string(.)').get().lower()
                            keywords = [k.strip().lower() for k in rule.detail_trigger_text.split(',')]
                            # If NONE of the keywords are found, skip deep dive
                            if not any(k in card_text for k in keywords):
                                perform_deep_dive = False
                                logger.debug(f"⚡ Fast-track: No trigger '{rule.detail_trigger_text}' found. Skipping deep dive.")

                        # Douglas often shows one price ("87,50 € · 30 ml") even when the
                        # product has several volumes — the "no …" prefix appears only
                        # sometimes. Its card data says whether there are variants.
                        if (not perform_deep_dive and rule.use_detail_page
                                and rule.detail_variant_selector != "SKIP" and rule.domain not in self.detail_skip_domains
                                and "douglas.lv" in current_url.lower()
                                and self._douglas_card_has_variants(card)):
                            perform_deep_dive = True

                        # Douglas: single-variant products have empty variant_name on detail pages;
                        # pull volume from catalog card's data-tealium-info so we don't lose it.
                        catalog_volume = None
                        if "douglas.lv" in current_url.lower():
                            catalog_volume = self._extract_douglas_catalog_volume(card)
                            if catalog_volume and not re.search(r'\d+\s*(ml|l|oz)\b', title, re.IGNORECASE):
                                title = f"{title} {catalog_volume}".strip()

                        if perform_deep_dive:
                            # --- PHASE 1: Collect deep-dive job (no blocking IO here) ---
                            deep_dive_queue.append({
                                "url": product_url,
                                "title": title,
                                "brand": brand,
                                "image_url": image_url,
                                "catalog_volume": catalog_volume,
                                "catalog_concentration": catalog_concentration,
                                "card_type": card_kind,
                            })
                        else:
                            # Standard mode: process variants from card JSON if available
                            from app.services.normalizer import perfume_normalizer
                            norm = perfume_normalizer.extract_all(title)
                            # DOM-sourced concentration (rule.concentration_css) wins over
                            # title-parsed one — the dedicated element is more reliable.
                            if catalog_concentration:
                                norm["concentration"] = catalog_concentration
                            listing_variants = self._extract_variants(card, norm["clean_name"])
                            if listing_variants:
                                for v in listing_variants:
                                    self._add_candidate(candidates, v["title"], v["price"], v["price"]>0, product_url, image_url, brand, norm, card_type=card_kind)
                            else:
                                self._add_candidate(candidates, title, price_val, is_available, product_url, image_url, brand, norm, card_type=card_kind)
                        
                    except Exception as e:
                        logger.debug(f"Error parsing card: {e}")
                        continue

                items_completed_overall = processed_cards - len(deep_dive_queue)
                if db and site_name_ui:
                    progress_pct = round((items_completed_overall / max_items) * 100, 1)
                    mode_text = "Parsing" if len(deep_dive_queue) == 0 else "Found"
                    db.update_status(site_name_ui, f"{mode_text}: {items_completed_overall}/{max_items}", progress=progress_pct)

                # --- PHASE 2: SEQUENTIAL DEEP DIVES (concurrent = 429 without proxy rotation) ---
                if deep_dive_queue:
                    domain_key = urlparse(current_url).netloc.replace("www.", "")
                    
                    # Prevent 429 Too Many Requests by limiting concurrency strictly
                    # Config looked up from DOMAIN_DEEP_DIVE_CONFIG; falls back to _default for unknown domains
                    _dd_cfg = DOMAIN_DEEP_DIVE_CONFIG.get(domain_key, DOMAIN_DEEP_DIVE_CONFIG["_default"])
                    concurrent_limit = _dd_cfg["concurrent"]
                    def delay_fn(_cfg=_dd_cfg): return random.uniform(_cfg["delay_min"], _cfg["delay_max"])

                    logger.info(f"🔍 Concurrent deep dives: {len(deep_dive_queue)} products (limit {concurrent_limit})")
                    
                    semaphore = asyncio.Semaphore(concurrent_limit) # Control burst load
                    
                    async def process_job(job):
                        async with semaphore:
                            await asyncio.sleep(delay_fn())
                            url = job["url"]
                            title = job["title"]
                            brand = job["brand"]
                            image_url = job["image_url"]
                            catalog_volume = job.get("catalog_volume")
                            catalog_concentration = job.get("catalog_concentration")
                            details = await self.scrape_product_details(url, rule, session=session, browser_context=None)

                            results = []
                            for d in details:
                                suffix = (d.get("title_suffix") or "").strip()
                                if suffix:
                                    # Variant explicitly knows its volume. The catalog `title` already
                                    # has the PRIMARY variant's volume baked in (e.g. "Polo 67 40 ml")
                                    # — leaving it in would create titles like "Polo 67 40 ml 125 ml"
                                    # and normalizer.extract_all picks the FIRST volume it sees, so
                                    # every variant would collapse to the same `volume` and dedup
                                    # by `(url, volume)` would merge them in `_flush_candidates`.
                                    # Strip any leading volume token from base title first —
                                    # with its pack count and pack label ("3x20 ml Refill"),
                                    # otherwise the primary variant's "Refill" leaks into
                                    # every other variant's title.
                                    base = re.sub(
                                        r'\b(?:\d+\s*[x×]\s*)?\d+(?:[.,]\d+)?\s*(ml|l|oz)\b'
                                        r'(?:\s+(?:refill|uzpilde|without stand|bez statīva)\b)?',
                                        '', title, flags=re.IGNORECASE
                                    )
                                    base = re.sub(r'\s+', ' ', base).strip()
                                    full_title = f"{base} {suffix}".strip()
                                else:
                                    # Single-variant Douglas product (empty suffix). Keep catalog title
                                    # as-is and fall back to catalog_volume if title has no ml token.
                                    full_title = title
                                    if catalog_volume and not re.search(r'\d+\s*(ml|l|oz)\b', full_title, re.IGNORECASE):
                                        full_title = f"{full_title} {catalog_volume}".strip()
                                results.append({
                                    "url": self._variant_url(url, d.get("item_id")),
                                    "image_url": image_url,
                                    "brand": brand,
                                    "title": full_title,
                                    "price": d["price"],
                                    "is_available": d["is_available"],
                                    "catalog_concentration": catalog_concentration,
                                    "card_type": job.get("card_type"),
                                })
                            return results

                    if db and site_name_ui:
                        progress_pct = round((items_completed_overall / max_items) * 100, 1)
                        db.update_status(site_name_ui, f"Deep Diving: {items_completed_overall}/{max_items}", progress=progress_pct)

                    tasks = [process_job(job) for job in deep_dive_queue]
                    from app.services.normalizer import perfume_normalizer
                    for f in asyncio.as_completed(tasks):
                        res = await f
                        for d in res:
                            base_norm = perfume_normalizer.extract_all(d["title"])
                            if d.get("catalog_concentration") and not base_norm.get("concentration"):
                                base_norm["concentration"] = d["catalog_concentration"]
                            # DEBUG (S20.1): log what we pass to _add_candidate to track
                            # how multi-variant products collapse to a single Product row.
                            logger.info(
                                f"  📥 Add candidate: title={d['title']!r}  "
                                f"volume={base_norm.get('volume')!r}  url={d['url']!r}"
                            )
                            self._add_candidate(
                                candidates, d["title"], d["price"], d["is_available"],
                                d["url"], d["image_url"], d["brand"], base_norm,
                                card_type=d.get("card_type"),
                            )
                        items_completed_overall += 1
                        if db and site_name_ui:
                            progress_pct = round((items_completed_overall / max_items) * 100, 1)
                            db.update_status(site_name_ui, f"Deep Diving: {items_completed_overall}/{max_items}", progress=progress_pct)
                        
                    deep_dive_queue.clear()

            finally:
                logger.debug("🚜 Finished processing catalog page.")

            # Flush this page's candidates to DB immediately — crash/Ctrl+C safe
            page_saved = await self._flush_candidates(session, candidates, rule, group_id, intent)
            final_scraped_items.extend(page_saved)
            candidates.clear()

            if processed_cards >= max_items:
                logger.info(f"🛑 Reached max_items limit ({max_items}). Stopping pagination.")
                break

            # --- PAGINATION ---
            # --- PAGINATION (Hybrid: Link vs Click) ---
            next_page_link = None

            # Sites with reliable ?page=N URL pagination — skip the AI click
            # selector (which gets intercepted by overlays / hits disabled
            # buttons on the last page) and just increment the query param.
            # The outer loop's seen_page_signatures stops us when the site
            # returns a duplicate page (i.e. real end of catalog).
            url_pattern_domains = ("220.lv", "1a.lv")
            if any(d in domain for d in url_pattern_domains):
                fallback = self._find_next_page_fallback(sel, current_url)
                if fallback:
                    next_page_link = fallback

            # Notino uses JS-rendered pagination (React spans, no <a href>).
            # The "next page" chevron is a div with data-testid="page-button-wrapper"
            # and class "nextPage". When it's present in DOM, click it.
            if "notino.lv" in domain and not next_page_link:
                notino_next = sel.css("[data-testid='page-button-wrapper'].nextPage")
                if notino_next:
                    next_click_selector = "[data-testid='page-button-wrapper'].nextPage"
                    logger.info("⏭️ Notino: nextPage chevron found — will click.")

            # 1. Try Rule-based selector
            if not next_page_link and not next_click_selector and rule.next_page_css:
                # Try finding HREF first (Standard link)
                try: 
                    el_list = sel.css(rule.next_page_css)
                    if el_list:
                        el = el_list[0]
                        href = el.attrib.get('href') or el.css('a::attr(href)').get()
                        
                        if href and not href.startswith('#') and not href.startswith('javascript'):
                             next_page_link = urljoin(current_url, href)
                        else:
                             # JS BUTTON DETECTED!
                             # If we found the element but no valid href, assume it needs a CLICK.
                             logger.info(f"⏭️ JS Pagination detected (No href). Will click {rule.next_page_css}...")
                             next_click_selector = rule.next_page_css
                             # We don't change 'current_url' variable, but next scrape_page call will use 'click_selector'
                             # Increment page count logic handled below
                except Exception as e:
                    logger.debug(f"Pagination check failed: {e}")

            # 2. Fallback logic (only if no click selector found)
            if not next_page_link and not next_click_selector:
                 # Check for fallback links
                 fallback = self._find_next_page_fallback(sel, current_url)
                 if fallback: next_page_link = fallback

            # --- DECISION ---
            if next_page_link and next_page_link != current_url:
                # Case A: Standard URL Navigation
                current_url = next_page_link
                page_number += 1
                html = None # Reset HTML for next loop
                
                # Checkpoint
                rule.last_page_url = current_url
                rule.items_scraped_current_run = processed_cards
                session.add(rule)
                await session.commit()
                
                logger.info(f"➡️ Navigating to Page {page_number}: {current_url}")
                await asyncio.sleep(random.uniform(settings.PAGE_DELAY_MIN, settings.PAGE_DELAY_MAX))

            elif next_click_selector:
                # Case B: JS Click Navigation
                # current_url remains same (base), but action changes
                page_number += 1
                html = None
                
                logger.info(f"👆 Clicking to Page {page_number}...")
                await asyncio.sleep(random.uniform(settings.PAGE_DELAY_MIN, settings.PAGE_DELAY_MAX))
                
            else:
                # Case C: End of Road
                logger.info("⏹️ Pagination finished (or limit reached).")
                # Reset Checkpoint
                rule.last_page_url = None
                rule.items_scraped_current_run = 0
                session.add(rule)
                await session.commit()
                if db and site_name_ui:
                    db.update_status(site_name_ui, "Finishing...", 100)
                break

            if rule_updated:
                session.add(rule)
            
            await session.commit()
            
            # --- UI UPDATE ---
            if db and site_name_ui:
                progress = min(100, int((len(candidates) / max_items) * 100))
                db.update_status(site_name_ui, f"Scanning (Found {len(candidates)} items)", progress)
                db.update_log(site_name_ui, f"Page {page_number}: Found {len(cards)} cards")
        
        # Reset Checkpoint if we finished successfully (reached limit or end)
        # We check processed_cards vs max_items because if we resume at EXACTLY the limit, 
        # the loop is skipped and we must clear the checkpoint to avoid a zombie state.
        if processed_cards >= max_items or (page_number > 1 and not next_page_link and not next_click_selector):
            rule.last_page_url = None
            rule.items_scraped_current_run = 0
            session.add(rule)
            await session.commit()
            logger.info(f"🏁 Checkpoint reset for {domain} (Reached limit or end).")

        # --- QUALITY CONTROL & SELF-LEARNING ---
        # Candidates were already saved per-page via _flush_candidates.
        report = self.validate_dataset(final_scraped_items)
        
        from datetime import datetime
        rule.health_score = report["score"]
        
        if report["is_healthy"]:
            rule.last_success = datetime.utcnow()
            rule.success_count += 1
            rule.last_error = None
            logger.success(f"💎 Data quality confirmed: {report['score']} ({len(final_scraped_items)} items)")
            await self.learn_from_success(session, rule)
        else:
            rule.failure_count += 1
            rule.last_error = report.get("error", "Unknown error")
            logger.warning(f"💊 Low data quality: {report['score']} | Error: {rule.last_error}")

        session.add(rule)
        await session.commit()

        try:
            await persistent_context.close()
        except Exception:
            pass

        return final_scraped_items


    async def _flush_candidates(self, session, candidates: list, rule, group_id, intent: dict | None) -> list:
        """Filter and save a batch of candidates to DB. Returns saved ScrapedItems.
        Called after each catalog page so data is committed incrementally — crash/Ctrl+C safe.
        """
        if not candidates:
            return []

        import json
        from datetime import datetime as _dt
        from app.services.validator import content_validator
        from app.services.matcher import matcher_service
        from app.domain.models import ProductGroup
        from app.services.notifier import notification_service
        from app.services.notification_dispatcher import dispatcher
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        # --- Filter ---
        all_forbidden: list = []
        if intent:
            all_forbidden = intent.get("forbidden_keywords", []).copy()
        if rule.negative_keywords:
            try:
                ctx = json.loads(rule.negative_keywords)
                if isinstance(ctx, list):
                    all_forbidden.extend(ctx)
            except Exception:
                pass

        # Alerts collected here and dispatched AFTER commit — see dispatch block below.
        pending_alerts: list[tuple] = []  # (product, history, percent_change)

        valid_items = []
        for item in candidates:
            if intent:
                if content_validator.is_garbage(item["title"], all_forbidden):
                    continue
                if not content_validator.check_brand(item["title"], intent.get("brand")):
                    continue
            valid_items.append(item)

        # --- Save ---
        saved_items = []
        is_sqlite = session.bind.dialect.name == "sqlite"
        insert_fn = sqlite_insert if is_sqlite else pg_insert

        for item in valid_items:
            stmt = select(Product).where(
                Product.url == item["url"],
                Product.volume == item["volume"]
            )
            product = (await session.execute(stmt)).scalar_one_or_none()
            if product is None and rule.domain == "douglas.lv" and "?" in item["url"]:
                # Older Douglas rows carry whichever ?item= the catalog card had at
                # the time; the same product page + volume is the same variant.
                path = item["url"].split("?", 1)[0]
                legacy = select(Product).where(
                    Product.search_term == "douglas.lv",
                    Product.volume == item["volume"],
                    or_(Product.url == path, Product.url.startswith(path + "?")),
                ).order_by(Product.last_seen.desc()).limit(1)
                product = (await session.execute(legacy)).scalar_one_or_none()
                if product is not None:
                    product.url = item["url"]
            elif product is None and rule.domain == "notino.lv":
                # Notino links a card to one of its variants (".../p-16228733/") and
                # picks a different one from run to run; the page without the
                # /p-…/ part + volume is the same variant.
                base = re.sub(r"p-\d+/?$", "", item["url"])
                legacy = select(Product).where(
                    Product.search_term == "notino.lv",
                    Product.volume == item["volume"],
                    or_(Product.url == base, Product.url.like(base + "p-%")),
                ).order_by(Product.last_seen.desc()).limit(1)
                product = (await session.execute(legacy)).scalar_one_or_none()
                if product is not None:
                    product.url = item["url"]

            card_type = item.get("card_type") or "perfume"
            price = item["price"]
            if price is not None and price > MAX_PLAUSIBLE_PRICE:
                logger.warning(f"Ignoring placeholder price {price} € for {item['title']} ({item['url']})")
                price = None
            has_price = price is not None and price > 0
            available = bool(item["is_available"])
            final_group_id = group_id
            # Gift sets never join a comparison chain.
            if not final_group_id and card_type == "perfume":
                # A new title (normalizer fix, the shop renamed the product)
                # gets matched again; an unchanged one keeps its group.
                if product and product.group_id and product.title == item["title"]:
                    final_group_id = product.group_id
                else:
                    match = await matcher_service.find_best_match(session, item)
                    if match:
                        final_group_id = match.id
                    else:
                        canonical = matcher_service.get_canonical_name(
                            item["title"],
                            brand=item.get("brand"),
                            concentration=item.get("concentration"),
                        )
                        upsert_stmt = insert_fn(ProductGroup).values(
                            name=canonical,
                            category="Perfume",
                            created_at=_dt.utcnow()
                        ).on_conflict_do_nothing(index_elements=["name"])
                        await session.execute(upsert_stmt)
                        await session.flush()
                        result = await session.execute(select(ProductGroup).where(ProductGroup.name == canonical))
                        resolved_group = result.scalar_one()
                        final_group_id = resolved_group.id
                        logger.info(f"✨ Created NEW Chain: {canonical}")

            if not product:
                product = Product(
                    title=item["title"],
                    url=item["url"],
                    # search_term tracks the store-of-origin and is what the
                    # catalog/feed filters by (LIKE '%notino%' etc). MUST be the
                    # canonical domain ('notino.lv', '220.lv', ...) — NOT
                    # rule.site_name which defaults to 'Unknown Shop' when AI
                    # doesn't populate it, breaking store filters silently.
                    search_term=rule.domain,
                    group_id=final_group_id,
                    brand=item.get("brand"),
                    volume=item.get("volume"),
                    concentration=item.get("concentration"),
                    card_type=card_type,
                )
                session.add(product)
                await session.flush()
                change_type = "initial" if has_price else "no_change"
            else:
                if card_type == "gift_set" or not group_id:
                    # Earlier runs stored makeup.lv sets as plain perfumes inside
                    # a chain — detach them. A perfume takes the group matched above.
                    product.group_id = final_group_id
                elif not product.group_id:
                    product.group_id = final_group_id
                product.card_type = card_type
                if not product.brand: product.brand = item.get("brand")
                if not product.volume: product.volume = item.get("volume")
                if not product.concentration: product.concentration = item.get("concentration")
                # Always overwrite title with the freshly-computed clean display_title.
                # This heals old records that were saved before the clean-title pipeline existed.
                product.title = item["title"]

                change_type = "no_change"
                if has_price and product.last_price:  # 0 / None = price never known
                    if price < product.last_price:
                        change_type = "price_down"
                        product.old_price = product.last_price
                    elif price > product.last_price:
                        change_type = "price_up"
                        product.old_price = product.last_price
                elif has_price:
                    change_type = "initial"
                if available and not product.is_available and has_price:
                    change_type = "back_in_stock"
                elif not available and product.is_available:
                    change_type = "out_of_stock"
                session.add(product)

            product.last_seen = _dt.utcnow()
            # Keep the last known price while a product has none (out of stock);
            # 0 marks a product that has never had a price.
            if has_price:
                product.last_price = price
            elif product.last_price is None:
                product.last_price = Decimal("0.00")
            product.is_available = available
            # Price with a promo code: taken fresh every time, so an ended
            # promotion clears it.
            product.promo_price = item.get("promo_price")
            product.promo_code = item.get("promo_code")
            if item["image_url"]:
                product.image_url = item["image_url"]

            if not product.brand and item.get("title"):
                from app.services.normalizer import perfume_normalizer
                norm = perfume_normalizer.extract_all(item["title"])
                product.brand = norm.get("brand")

            session.add(product)

            history_price = price if has_price else product.last_price
            if change_type != "no_change" and history_price and history_price > 0:
                history = PriceHistory(
                    price=history_price,
                    in_stock=available,
                    product_id=product.id,
                    change_type=change_type
                )
                session.add(history)
                notification_service.report_change(product, history, rule.site_name)
                if change_type in ("price_down", "price_up", "back_in_stock"):
                    pct = self._compute_percent_change(history_price, product.old_price)
                    pending_alerts.append((product, history, pct))

            saved_items.append(ScrapedItem(
                title=product.title,
                price=price if has_price else None,
                availability="Yes" if available else "No",
                url=product.url,
                image_url=item["image_url"]
            ))

        await session.commit()
        logger.info(f"💾 Page flushed: {len(saved_items)} items saved.")

        # Dispatch AFTER commit — transport failure must not roll back PriceHistory.
        for product, history, pct in pending_alerts:
            try:
                await dispatcher.dispatch_price_alert(session, product, history, pct)
            except Exception as exc:
                logger.error(f"Alert dispatch failed for product {product.id}: {exc}")

        return saved_items

    @staticmethod
    def _compute_percent_change(new_price, old_price) -> float:
        """Signed percent change: negative = price drop."""
        try:
            if not old_price or float(old_price) == 0:
                return 0.0
            return (float(new_price) - float(old_price)) / float(old_price) * 100
        except Exception:
            return 0.0

    @staticmethod
    def _variant_url(url: str, item_id: str | None) -> str:
        """Douglas: point the URL at the variant's own ?item= id, so one variant
        always keeps one URL (a product is identified by url + volume)."""
        if not item_id:
            return url
        if re.search(r"[?&]item=\d+", url):
            return re.sub(r"([?&])item=\d+", rf"\g<1>item={item_id}", url)
        return f"{url}{'&' if '?' in url else '?'}item={item_id}"

    def _add_candidate(self, candidates, title, price, is_available, url, image_url, brand, norm, card_type=None,
                       promo_price=None, promo_code=None):
        """Standardizes and adds a product to the candidates list.

        Builds a clean display title: "{brand} {clean_name} {volume}".
        Raw scraped title (with Latvian fluff / EDT/EDP markers) is discarded —
        concentration lives in its own column, not the title.

        Non-perfume listings (deodorants, body sprays, aftershaves, shampoos,
        shower gels) are rejected here on the RAW title — once normalization
        strips the 'dezodorants'/'deo' marker, the product becomes
        indistinguishable from a real perfume and pollutes the DB.

        `card_type` is "perfume" or "gift_set"; detected from the title when the
        caller doesn't know it. A set that includes e.g. a shower gel is still
        a set, so set detection runs before the non-perfume filter.
        """
        from app.services.normalizer import (
            perfume_normalizer, is_non_perfume_title, detect_card_type, is_non_perfume_set, volume_qualifier,
        )

        card_type = card_type or detect_card_type(title)
        if card_type == "gift_set" and is_non_perfume_set(title):
            logger.debug(f"🚫 Rejected set without perfume: {title}")
            return
        if card_type != "gift_set" and is_non_perfume_title(title):
            logger.debug(f"🚫 Rejected non-perfume: {title}")
            return

        v_norm = perfume_normalizer.extract_all(title, explicit_brand=brand)

        # v_norm["brand"] is the shop's brand in its one display spelling
        final_brand = v_norm["brand"] or norm["brand"]
        final_volume = v_norm["volume"] or norm["volume"]
        final_concentration = v_norm["concentration"] or norm["concentration"]

        if card_type == "gift_set":
            # A set holds several items: no single volume or concentration, and
            # the raw title (with its composition) is the honest description.
            display_title = re.sub(r"\s+", " ", title).strip()
            # Compare letters only: shops spell brands with ` vs ' ("Tesori d`Oriente").
            if final_brand and not re.sub(r"\W+", "", display_title.lower()).startswith(re.sub(r"\W+", "", final_brand.lower())):
                display_title = f"{final_brand} {display_title}"
            # A set sold in several packs ("3x20 ml" and "3x20 ml Refill") needs a
            # label per pack, or the packs would share one (url, volume) record.
            # A composition in brackets ("(edp/mini/3x15ml)") is not a pack label.
            pack = re.search(r"(\d+)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*(ml|g)\b",
                             re.sub(r"\([^)]*\)", "", title), re.IGNORECASE)
            set_volume = None
            if pack:
                set_volume = f"{pack.group(1)}x{pack.group(2).replace(',', '.')}{pack.group(3).lower()}"
                if volume_qualifier(title):
                    set_volume += f" {volume_qualifier(title)}"
            candidates.append({
                "url": url,
                "image_url": image_url,
                "brand": final_brand,
                "volume": set_volume,
                "concentration": None,
                "title": display_title,
                "price": price,
                "is_available": is_available,
                "card_type": "gift_set",
                "promo_price": promo_price,
                "promo_code": promo_code,
            })
            return

        # "100 ml Refill" is a different product than the 100 ml bottle: keep
        # the pack in the volume label so the two never share a record.
        qualifier = volume_qualifier(title)
        if final_volume and qualifier:
            final_volume = f"{final_volume} {qualifier}"
        clean_name = v_norm.get("clean_name") or ""

        # Strip stray punctuation from each part BEFORE concatenation —
        # otherwise ":" / "?" / "'s" gets sandwiched between clean_name and volume
        # and the final .strip() at the end never sees it.
        _PUNCT = " ,.:;?!'\"|-–—"
        clean_name = clean_name.strip(_PUNCT)
        if final_brand:
            final_brand = final_brand.strip(_PUNCT)
        # Drop clean_name leftovers like a lone "s" / "'" / ":" after stripping
        if clean_name and len(clean_name) <= 2 and not any(c.isalnum() for c in clean_name):
            clean_name = ""

        parts = [p for p in [final_brand, clean_name, final_volume] if p]
        display_title = " ".join(parts).strip()

        # Collapse accidental brand duplication ("Guy Laroche Guy Laroche Drakkar")
        if final_brand:
            display_title = re.sub(
                rf'\b({re.escape(final_brand)})(\s+\1\b)+',
                r'\1',
                display_title,
                flags=re.IGNORECASE,
            )
            display_title = re.sub(r'\s+', ' ', display_title).strip()

        # Trim trailing punctuation artifacts ("Name :", "Name ?", "brand's")
        display_title = display_title.strip(" ,.:;?!'\"|-–—")

        # Fallback: if normalization produced garbage (empty / too short),
        # keep the raw title so we never lose the product identity.
        if len(display_title) < 3:
            display_title = title

        candidates.append({
            "url": url,
            "image_url": image_url,
            "brand": final_brand,
            "volume": final_volume,
            "concentration": final_concentration,
            "title": display_title,
            "price": price,
            "is_available": is_available,
            "card_type": card_type,
            "promo_price": promo_price,
            "promo_code": promo_code,
        })

    async def scrape_page(self, url: str, rule: ScrapingRule | None = None, browser_context=None, click_selector: str | None = None) -> dict | None:
        """
        Fetches HTML content using Stealth Browser.
        Supports click_selector for JS pagination.
        """
        fast_mode = True 
        try:
             # Logic to adjust speed based on rule can go here
             pass
        except: pass
        
        # If click_selector is present, we MUST use browser_manager
        if click_selector:
             from app.core.browser import browser_manager
             return await browser_manager.get_page_content(
                url, 
                fast_mode=fast_mode, 
                context=browser_context, 
                click_selector=click_selector
             )

        # SPA sites — stealth client returns empty product shells (200 OK but no card content).
        # Must always use full browser for correct React/JS rendering.
        # 220.lv: CF blocks the second request in a shared context. Use a fresh context
        # per page (each page = first request = no CF challenge).
        if "220.lv" in url:
            from app.core.browser import browser_manager
            return await browser_manager.get_page_content(url, fast_mode=fast_mode, context=None)
        if "notino.lv" in url:
            from app.core.browser import browser_manager
            return await browser_manager.get_page_content(url, fast_mode=fast_mode, context=browser_context)
        # 1a.lv: the HTML has no products (LupaSearch renders them in the browser).
        # Its catalog is behind a Cloudflare check: only wait, never answer it.
        if "1a.lv" in url:
            from app.core.browser import browser_manager
            return await browser_manager.get_page_content(url, fast_mode=fast_mode, context=browser_context, solve_cf=False)

        # Otherwise try stealth client (fast) first, but return dict format
        html = await stealth_client.get_page(url)
        if html and "202 Accepted" not in html:
            return {"html": html, "url": url}
            
        # Fallback to browser
        from app.core.browser import browser_manager
        return await browser_manager.get_page_content(
            url, 
            fast_mode=fast_mode, 
            context=browser_context
        )

    async def close(self):
        if 'app.core.browser' in sys.modules:
             from app.core.browser import browser_manager
             await browser_manager.stop()

scraper_service = ScraperService()