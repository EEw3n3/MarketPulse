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
)

@dataclass
class ScrapedItem:
    title: str
    price: Decimal
    availability: str
    url: str
    image_url: Optional[str] = None
    is_valid: bool = True
    validation_error: str = ""


class ScraperService:
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
        zero_prices = sum(1 for i in items if i.price <= 0)
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
        """
        Navigates to the page, clicks variants, and intercepts JSON payloads
        to perfectly extract price and volume data.
        """
        import json
        from playwright.async_api import async_playwright
        from app.core.browser import browser_manager
        from app.core.constants import COOKIE_ACCEPT_BUTTONS, OUT_OF_STOCK_PHRASES, MEASUREMENT_UNITS
        
        logger.info(f"🕷️ [Network Intercept] Deep dive: {url}")
        variants = []
        
        context = await browser_manager.get_context()
        page = await context.new_page()
        
        intercepted_requests = {"luigisbox": [], "detail": []}
        
        async def handle_request(request):
            try:
                req_url = request.url
                if request.method in ["POST", "PUT"]:
                    # СТРОГОЕ ПРАВИЛО ДЛЯ ЦЕНЫ: collector-lv.notino.luigisbox.com/events
                    if "collector-lv.notino.luigisbox.com/events" in req_url:
                        post_data = request.post_data_json
                        if post_data:
                            intercepted_requests["luigisbox"].append(post_data)
                    # ПРАВИЛО ДЛЯ ОБЪЕМА И НАЛИЧИЯ: detail api
                    elif "/api/tracking/web/view/detail" in req_url:
                        post_data = request.post_data_json
                        if post_data:
                            intercepted_requests["detail"].append(post_data)
            except Exception:
                pass
                
        page.on("request", handle_request)
        
        try:
            # Block images for speed
            await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,ico}", lambda route: route.abort())
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # Auto-accept cookies so they don't block our clicks
            cookie_selectors = COOKIE_ACCEPT_BUTTONS
            
            # Wait up to 3 seconds for cookie banner to load, Notino is slow with React
            await asyncio.sleep(1.0)
            
            for btn_sel in cookie_selectors:
                cookie_btn = page.locator(btn_sel).first
                if await cookie_btn.is_visible(timeout=1000):
                    await cookie_btn.click(force=True)
                    await asyncio.sleep(0.5)
                    break
            
            await asyncio.sleep(0.5) # Wait for initial trackers 
            
            # Find and click variants
            # Expanded selectors to include visual image tiles (Scandal Elixir style)
            variant_els = await page.locator("div[data-testid*='variant'], span[class*='variant'], .pd-variant-label, [data-testid='product-variants'] > div, div[class*='VariantContainer'] > div").all()
            if not variant_els:
                variant_els = await page.locator("div:has-text(' ml'), button:has-text(' ml')").all()
                
            # Phase 1: Click all variants to force network traffic
            dom_variants_map = {}
            import re
            for i, el in enumerate(variant_els):
                if await el.is_visible():
                    try:
                        text = await el.inner_text()
                        vol = ""
                        units_pattern = '|'.join(MEASUREMENT_UNITS)
                        m_vol = re.search(rf'(\d+(?:[.,]\d+)?\s*({units_pattern}))', text, re.IGNORECASE)
                        if m_vol:
                            vol = m_vol.group(1).lower().replace(' ', '')
                            unit_match = m_vol.group(2).lower()
                            vol = vol.replace(unit_match, f' {unit_match}')
                            
                            text_lower = text.lower()
                            is_avail = not any(phrase in text_lower for phrase in OUT_OF_STOCK_PHRASES)
                            
                            if vol not in dom_variants_map or dom_variants_map[vol]["price"] == 0.0:
                                dom_variants_map[vol] = {
                                    "price": 0.0,
                                    "available": is_avail
                                }
                            
                        # Re-attempt if cookies block the very first click
                        if i == 0:
                            for btn_sel in cookie_selectors:
                                btn = page.locator(btn_sel).first
                                if await btn.is_visible(timeout=100):
                                    await btn.click(force=True)
                                    await asyncio.sleep(0.5)
                        
                        await el.click(timeout=1500, force=True)
                        # 0.8s is a sweet spot: lets React update the screen price and bypasses strict analytics drop
                        await asyncio.sleep(0.8)
                        
                        # Perfect Fallback: Read visually updated price directly from the screen
                        if vol and dom_variants_map[vol]["price"] == 0.0 and dom_variants_map[vol]["available"]:
                            try:
                                main_price = await page.locator("[data-testid='price-component']").first.inner_text(timeout=500)
                                p_val = self.parse_price(main_price) if hasattr(self, 'parse_price') else 0.0
                                if not p_val:
                                    m_pr = re.search(r'(\d+[,.]\d+)', main_price)
                                    if m_pr: p_val = float(m_pr.group(1).replace(',', '.'))
                                if p_val:
                                    dom_variants_map[vol]["price"] = p_val
                            except Exception:
                                pass
                    except Exception:
                        pass
                        
            # Wait for any straggler network requests to land
            await asyncio.sleep(1.0)
            
            variants_map = {}
            
            # Phase 2: Parse all /detail payloads for Volume and Availability
            for req_data in intercepted_requests["detail"]:
                code = req_data.get("code")
                if code:
                    size = req_data.get("size")
                    sizeUnit = req_data.get("sizeUnit")
                    is_available = req_data.get("stockQuantity") != "outOfStock"
                    if size and sizeUnit:
                        variants_map[code] = {
                            "volume": f"{size} {sizeUnit}",
                            "available": is_available
                        }
                        
            # Phase 3: Parse all luigisbox payloads for Price
            for req_data in intercepted_requests["luigisbox"]:
                events = req_data.get("events", [])
                for event in events:
                    event_data = event.get("data", {})
                    
                    products = list(event_data.get("products", []))
                    if "related_to" in event_data:
                        products.extend(event_data["related_to"].get("products", []))
                         
                    for p in products:
                        p_code = p.get("product_code")
                        # Match prices ONLY to variants we saw in /detail
                        if p_code and p_code in variants_map:
                            p_discount = p.get("discount_price")
                            p_full = p.get("full_price")
                            
                            # Strict Rule 1 and 3: Use discount_price, fallback to full_price
                            found_price = p_discount if p_discount is not None else p_full
                            if found_price is not None:
                                variants_map[p_code]["price"] = found_price
                                
            # Phase 4: Assemble Final Deduplicated List
            seen_volumes = set()
            for code, data in variants_map.items():
                if "price" in data and data["price"] != 0.0 and data["price"] is not None:
                    vol = data["volume"].lower().replace(' ', '')
                    vol = vol.replace('ml', ' ml').replace('g', ' g')
                    if vol not in seen_volumes:
                        seen_volumes.add(vol)
                        variants.append({
                            "title_suffix": vol,
                            "price": Decimal(str(data["price"])).quantize(Decimal("0.01")),
                            "is_available": data["available"]
                        })
                        
            # Add missing DOM variants (e.g., out of stock ones that network ignored, or network failed prices)
            for vol, dom_data in dom_variants_map.items():
                if vol not in seen_volumes:
                    seen_price = dom_data.get("price")
                    if seen_price is None or seen_price == 0.0:
                        continue # Skip completely invalid DOM prices
                        
                    seen_volumes.add(vol)
                    variants.append({
                        "title_suffix": vol,
                        "price": Decimal(str(seen_price)).quantize(Decimal("0.01")),
                        "is_available": dom_data.get("available", True)
                    })
                    
            # Phase 5: Single Product Fallback (No buttons/variants)
            # Notino Single Variant Logic: Handle special volume location and promo prices
            if not variants:
                try:
                    # 1. Price Extraction (Prioritize Promo Price with Code)
                    price_val = 0.0
                    
                    # Direct JS check for promo block (e.g. "31,87 € ar kodu TOP")
                    # We look for the lowest price shown in the BuyBox area
                    price_val = await page.evaluate('''() => {
                        // Priority 1: Red promo price text
                        let promoEl = document.querySelector('div[class*="PromoPrice"], [data-testid*="promo-price"], span[class*="promo-price"]');
                        if (promoEl && promoEl.innerText.includes('€')) {
                             let m = promoEl.innerText.match(/(\d+[,.]\d+)/);
                             if (m) return parseFloat(m[1].replace(',', '.'));
                        }
                        
                        // Priority 2: Standard price component
                        let stdEl = document.querySelector('[data-testid="price-component"]');
                        if (stdEl) {
                             let m = stdEl.innerText.match(/(\d+[,.]\d+)/);
                             if (m) return parseFloat(m[1].replace(',', '.'));
                        }
                        return 0;
                    }''')
                        
                    # 2. Volume Extraction (Prioritize #pdSelectedVariant with JS override)
                    # Playwright inner_text() sometimes misses hidden-but-present text in React
                    vol_text = await page.evaluate('''() => {
                        let el = document.querySelector('#pdSelectedVariant');
                        return el ? el.innerText : '';
                    }''')
                    
                    vol = ""
                    units_pattern = '|'.join(MEASUREMENT_UNITS)
                    if vol_text:
                        m_sv = re.search(rf'(\d+(?:[.,]\d+)?\s*({units_pattern}))', vol_text, re.IGNORECASE)
                        if m_sv:
                            vol = m_sv.group(1).lower().replace(' ', '')
                            unit_m = m_sv.group(2).lower()
                            vol = vol.replace(unit_m, f' {unit_m}')
                    
                    if not vol:
                        # Fallback: scan whole page
                        full_text = await page.evaluate("document.body.innerText")
                        m_vol = re.search(rf'(\d+(?:[.,]\d+)?\s*({units_pattern}))', full_text, re.IGNORECASE)
                        if m_vol:
                            vol = m_vol.group(1).lower().replace(' ', '')
                            unit_match = m_vol.group(2).lower()
                            vol = vol.replace(unit_match, f' {unit_match}')
                        
                    if price_val:
                        variants.append({
                            "title_suffix": vol,
                            "price": Decimal(str(price_val)).quantize(Decimal("0.01")),
                            "is_available": True
                        })
                except Exception as e:
                    logger.debug(f"Single product fallback failed: {e}")
        except Exception as e:
            logger.error(f"Network intercept failed for {url}: {e}")
        finally:
            await page.close()
            
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
             if network_variants:
                 logger.success(f"🎯 Network intercept extracted {len(network_variants)} variants flawlessly.")
                 return network_variants
             else:
                 logger.warning("Network intercept returned 0 variants. Falling back to DOM parsing.")

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
                
                for match in tealium_matches:
                    text_match = match.group(1)
                    text_unescaped = html_lib.unescape(text_match)
                    try:
                        data = json.loads(text_unescaped)
                        
                        p_price_list = data.get("primary_product_price", [])
                        v_name_list = data.get("primary_product_variant_name", [])
                        stock_list = data.get("primary_product_availability_status", [])
                        
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
                                    "is_available": is_avail
                                })
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
                # If AI failed to find variants, set a marker so we don't try again in this run
                rule.detail_variant_selector = "SKIP"
                session.add(rule)
                await session.commit()

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
                rule.detail_variant_selector = "SKIP"
                if session:
                    session.add(rule)
                    await session.commit()
        
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
        from playwright_stealth import stealth_async

        ctx = await browser_manager.get_context()
        final_scraped_items: list = []

        from app.services.ui import get_dashboard
        db = get_dashboard()

        page = await ctx.new_page()
        try:
            await page.route(
                "**/*.{png,jpg,jpeg,gif,webp,svg,ico}",
                lambda route: route.abort()
            )
            await stealth_async(page)

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

                        perform_deep_dive = rule.use_detail_page
                        if rule.detail_variant_selector == "SKIP":
                            perform_deep_dive = False
                        elif perform_deep_dive and rule.detail_trigger_text:
                            card_text = card.xpath("string(.)").get().lower()
                            keywords = [k.strip().lower() for k in rule.detail_trigger_text.split(",")]
                            if not any(k in card_text for k in keywords):
                                perform_deep_dive = False

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
                        
                        # Use precise dynamic URL extracted from React state
                        if notino_pagination_fmt:
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
                            out = []
                            for d in details:
                                ft = f"{job['title']} {d['title_suffix']}".strip()
                                out.append({
                                    "url": job["url"],
                                    "image_url": job["image_url"],
                                    "brand": job["brand"],
                                    "title": ft,
                                    "price": d["price"],
                                    "is_available": d["is_available"],
                                    "catalog_concentration": None,
                                })
                            return out

                    tasks = [_process_job(j) for j in deep_dive_queue]
                    for f in asyncio.as_completed(tasks):
                        res = await f
                        for d in res:
                            norm = perfume_normalizer.extract_all(d["title"])
                            self._add_candidate(
                                candidates, d["title"], d["price"], d["is_available"],
                                d["url"], d["image_url"], d["brand"], norm
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
        from app.services.normalizer import perfume_normalizer

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

            offset = 0
            page_size = 36
            page_number = 1
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
                    base_norm = perfume_normalizer.extract_all(base_title)
                    if sub_title and not base_norm.get("concentration"):
                        sub_conc = perfume_normalizer.extract_all(sub_title).get("concentration")
                        if sub_conc:
                            base_norm["concentration"] = sub_conc

                    in_stock = bool(p.get("inStock"))
                    price_obj = p.get("price") or {}
                    fallback_price = Decimal(str(price_obj.get("current") or 0)).quantize(Decimal("0.01"))

                    variants_data = ((p.get("analytics") or {}).get("variantsData")) or {}
                    if isinstance(variants_data, dict) and variants_data:
                        for _vid, info in variants_data.items():
                            if not isinstance(info, dict):
                                continue
                            vol = (info.get("value") or "").strip()
                            v_price = Decimal(str(info.get("price") or 0)).quantize(Decimal("0.01"))
                            full_title = f"{base_title} {vol}".strip()
                            self._add_candidate(
                                candidates, full_title, v_price, v_price > 0,
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

        We use `regular_price` (publicly accessible non-loyalty price) rather
        than `price` (loyalty/PLUS members only) for fair cross-site comparison.
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
                image_url = data.get('photoUrl', '')
                brand     = dl.get('item_brand', '')
                status    = dl.get('item_status', 'active')

                # regular_price = standard retail price (non-loyalty)
                # price         = loyalty/PLUS member price (requires subscription)
                # 220.lv widget-data is inconsistent across deploys: sometimes int cents (4499),
                # sometimes float cents (2389.00), rarely float euros (44.99). Type-based detection
                # fails on float-cents. Use value-based heuristic: anything > 500 is cents (a single
                # perfume bottle at retail never exceeds 500€ in the Latvian market).
                def _norm_220_price(raw) -> Decimal:
                    if raw is None:
                        return Decimal('0.00')
                    v = Decimal(str(raw))
                    if v > Decimal('500'):
                        v = v / 100
                    return v.quantize(Decimal('0.01'))

                regular_price = _norm_220_price(dl.get('regular_price'))
                sell_price    = _norm_220_price(dl.get('price'))

                # Use regular_price as the reference; fall back to sell_price if missing
                final_price = regular_price if regular_price > 0 else sell_price
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
                    })
            except Exception as e:
                logger.debug(f'220.lv widget-data parse error: {e}')

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

    async def scrape_catalog(self, session, start_url: str, initial_html: str = None, max_items: int = 100, group_id: Optional[int] = None, intent: dict = None, enable_price_filter: bool = True, site_name_ui: str = None):
        domain = urlparse(start_url).netloc.replace("www.", "")
        
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
                    from app.services.normalizer import perfume_normalizer
                    unique_products_220 = set()
                    for mi in items_220:
                        lower_title = mi['base_title'].lower()
                        if any(b in lower_title for b in PRODUCT_BLACKLIST): continue
                        unique_products_220.add(mi['url'])
                        base_norm = perfume_normalizer.extract_all(mi['base_title'])
                        full_title = f"{mi['base_title']} {mi['volume']}".strip()
                        self._add_candidate(candidates, full_title, mi['price'], mi['is_available'], mi['url'], mi['image_url'], mi['brand'], base_norm)
                    processed_cards += len(unique_products_220)
                    cards = []  # Skip standard DOM loop
                    injection_ok = True
                    injection_signature = frozenset(unique_products_220)
                else:
                    logger.warning("⚠️ 220.lv widget-data yielded 0 items — falling back to DOM selectors")
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
                        if rule.detail_variant_selector == "SKIP":
                            perform_deep_dive = False
                        elif perform_deep_dive and rule.detail_trigger_text:
                            card_text = card.xpath('string(.)').get().lower()
                            keywords = [k.strip().lower() for k in rule.detail_trigger_text.split(',')]
                            # If NONE of the keywords are found, skip deep dive
                            if not any(k in card_text for k in keywords):
                                perform_deep_dive = False
                                logger.debug(f"⚡ Fast-track: No trigger '{rule.detail_trigger_text}' found. Skipping deep dive.")

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
                                    self._add_candidate(candidates, v["title"], v["price"], v["price"]>0, product_url, image_url, brand, norm)
                            else:
                                self._add_candidate(candidates, title, price_val, is_available, product_url, image_url, brand, norm)
                        
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
                                full_title = f"{title} {d['title_suffix']}".strip()
                                # Fallback: single-variant Douglas products have empty title_suffix;
                                # stitch catalog volume onto the title so normalizer can pick it up.
                                if catalog_volume and not re.search(r'\d+\s*(ml|l|oz)\b', full_title, re.IGNORECASE):
                                    full_title = f"{full_title} {catalog_volume}".strip()
                                results.append({
                                    "url": url,
                                    "image_url": image_url,
                                    "brand": brand,
                                    "title": full_title,
                                    "price": d["price"],
                                    "is_available": d["is_available"],
                                    "catalog_concentration": catalog_concentration,
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
                            self._add_candidate(
                                candidates, d["title"], d["price"], d["is_available"],
                                d["url"], d["image_url"], d["brand"], base_norm,
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

            final_group_id = group_id
            if not final_group_id:
                if product and product.group_id:
                    final_group_id = product.group_id
                else:
                    match = await matcher_service.find_best_match(session, item)
                    if match:
                        final_group_id = match.id
                    else:
                        canonical = matcher_service.get_canonical_name(item["title"], brand=item.get("brand"))
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
                    concentration=item.get("concentration")
                )
                session.add(product)
                await session.flush()
                change_type = "initial"
            else:
                if not product.group_id: product.group_id = final_group_id
                if not product.brand: product.brand = item.get("brand")
                if not product.volume: product.volume = item.get("volume")
                if not product.concentration: product.concentration = item.get("concentration")
                # Always overwrite title with the freshly-computed clean display_title.
                # This heals old records that were saved before the clean-title pipeline existed.
                product.title = item["title"]

                change_type = "no_change"
                if product.last_price is not None:
                    if item["price"] < product.last_price:
                        change_type = "price_down"
                        product.old_price = product.last_price
                    elif item["price"] > product.last_price:
                        change_type = "price_up"
                        product.old_price = product.last_price
                if not product.is_available and item["price"] > 0:
                    change_type = "back_in_stock"
                session.add(product)

            price_to_save = item["price"] if item["price"] is not None else Decimal("0.00")
            product.last_seen = _dt.utcnow()
            product.last_price = price_to_save
            product.is_available = item["is_available"]
            if item["image_url"]:
                product.image_url = item["image_url"]

            if not product.brand and item.get("title"):
                from app.services.normalizer import perfume_normalizer
                norm = perfume_normalizer.extract_all(item["title"])
                product.brand = norm.get("brand")

            session.add(product)

            if change_type != "no_change":
                history = PriceHistory(
                    price=item["price"],
                    in_stock=item["is_available"],
                    product_id=product.id,
                    change_type=change_type
                )
                session.add(history)
                notification_service.report_change(product, history, rule.site_name)
                pct = self._compute_percent_change(item["price"], product.old_price)
                pending_alerts.append((product, history, pct))

            saved_items.append(ScrapedItem(
                title=product.title,
                price=item["price"],
                availability="Yes",
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

    def _add_candidate(self, candidates, title, price, is_available, url, image_url, brand, norm):
        """Standardizes and adds a product to the candidates list.

        Builds a clean display title: "{brand} {clean_name} {volume}".
        Raw scraped title (with Latvian fluff / EDT/EDP markers) is discarded —
        concentration lives in its own column, not the title.

        Non-perfume listings (deodorants, body sprays, aftershaves, shampoos,
        shower gels) are rejected here on the RAW title — once normalization
        strips the 'dezodorants'/'deo' marker, the product becomes
        indistinguishable from a real perfume and pollutes the DB.
        """
        from app.services.normalizer import perfume_normalizer, is_non_perfume_title

        if is_non_perfume_title(title):
            logger.debug(f"🚫 Rejected non-perfume: {title}")
            return

        v_norm = perfume_normalizer.extract_all(title, explicit_brand=brand)

        final_brand = brand or v_norm["brand"] or norm["brand"]
        final_volume = v_norm["volume"] or norm["volume"]
        final_concentration = v_norm["concentration"] or norm["concentration"]
        clean_name = v_norm.get("clean_name") or ""

        # Strip stray punctuation from each part BEFORE concatenation —
        # otherwise ":" / "?" / "'s" gets sandwiched between clean_name and volume
        # and the final .strip() at the end never sees it.
        _PUNCT = " ,.:;?!'\"|-"
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
        display_title = display_title.strip(" ,.:;?!'\"|-")

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
            "is_available": is_available
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