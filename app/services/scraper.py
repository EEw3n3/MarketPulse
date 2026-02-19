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

        return None

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
    
    async def scrape_product_details(self, url: str, rule: ScrapingRule, session=None, browser_context=None) -> list[dict]:
        """
        Fetches the product page and extracts all available variants (volumes/prices).
        Uses AI to learn the structure if not already known.
        """
        logger.info(f"🔍 Deep dive: {url}")
        
        # Sites like Notino block StealthClient on detail pages, use Browser directly
        html = None
        if "notino.lv" in url:
            from app.core.browser import browser_manager
            resp = await browser_manager.get_page_content(url, fast_mode=True, context=browser_context)
            html = resp["html"] if resp else None
        else:
            html = await stealth_client.get_page(url)
            if not html or "captcha" in html.lower() or "403" in str(html) or "202 Accepted" in str(html):
                 from app.core.browser import browser_manager
                 resp = await browser_manager.get_page_content(url, fast_mode=True, context=browser_context)
                 html = resp["html"] if resp else None
             
        if not html: return []
        
        # --- SELF-LEARNING PHASE: If we don't have detail selectors, ask AI ---
        if not rule.detail_variant_selector and session:
            logger.warning(f"🧠 [Autonomous] Learning detail structure for {rule.domain}...")
            from app.services.ai_generator import ai_generator
            detail_data = await ai_generator.generate_detail_rule(url, html)
            
            if detail_data.get("variant_container_css"):
                rule.detail_variant_selector = detail_data.get("variant_container_css")
                rule.detail_variant_name_css = detail_data.get("variant_name_css")
                rule.detail_variant_price_css = detail_data.get("variant_price_css")
                session.add(rule)
                await session.commit()
                logger.success(f"🧠 [Autonomous] Saved detail rules for {rule.domain}")

        sel = Selector(text=html)
        variants = []
        
        # 1. Use AI-generated or manual selectors
        v_selector = rule.detail_variant_selector
        if v_selector:
            nodes = sel.css(v_selector)
            if not nodes:
                logger.debug(f"⚠️ Selector {v_selector} found 0 nodes on {url}. HTML length: {len(html)}")
                # If we expected variants but found none, maybe the selector is stale
                if "notino" in url and "pd-price" not in html:
                     logger.warning(f"🚩 Might be blocked or layout changed on {url}")

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
        
        # 2. IF 0 VARIANTS: Try one-time AI learning (without updating global rule if it flaps)
        if not variants and session:
            logger.warning(f"🤔 No variants found with stored rule for {url}. Trying one-time AI assist...")
            from app.services.ai_generator import ai_generator
            try:
                one_time_data = await ai_generator.generate_detail_rule(url, html)
                v_selector = one_time_data.get("variant_container_css")
                if v_selector:
                    nodes = sel.css(v_selector)
                    for node in nodes:
                        name_css = one_time_data.get("variant_name_css") or ".volume, .name"
                        price_css = one_time_data.get("variant_price_css") or ".price"
                        name_el, _ = self._try_selectors(node, name_css)
                        price_el, _ = self._try_selectors(node, price_css)
                        name_text = self.extract_clean_text(name_el)
                        price_text = self.extract_clean_text(price_el)
                        p_val = self.parse_price(price_text)
                        if name_text:
                            variants.append({
                                "title_suffix": name_text,
                                "price": p_val,
                                "is_available": p_val > 0
                            })
            except Exception as e:
                logger.error(f"AI Fallback failed: {e}")

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

    async def scrape_catalog(self, session, start_url: str, initial_html: str = None, max_items: int = 100, group_id: Optional[int] = None, intent: dict = None, enable_price_filter: bool = True, site_name_ui: str = None):
        domain = urlparse(start_url).netloc.replace("www.", "")
        
        statement = select(ScrapingRule).where(ScrapingRule.domain == domain)
        result = await session.execute(statement)
        rule = result.scalar_one_or_none()
        if not rule: return []

        candidates = [] 
        html = initial_html
        current_url = start_url
        page_number = 1
        processed_cards = 0
        next_click_selector = None # For JS Pagination

        # --- RESUME LOGIC (Checkpoint) ---
        if rule.last_page_url and rule.last_page_url.startswith(start_url.split('?')[0]):
            logger.info(f"🔄 Resuming from checkpoint: {rule.last_page_url}")
            current_url = rule.last_page_url
            processed_cards = rule.items_scraped_current_run
            html = None # Force fresh fetch
        
        from app.services.ui import get_dashboard
        db = get_dashboard()

        while processed_cards < max_items:
            # Check if we have a valid URL or a pending click
            if not current_url and not next_click_selector:
                break

            if db and site_name_ui:
                db.update_status(site_name_ui, f"Loading Page {page_number}")
            
            # --- FETCH PAGE ---
            # Now we delegate everything to scrape_page which handles clicks/browser internally
            page_response = await self.scrape_page(
                current_url, 
                rule=rule, 
                # passing None context for now to keep sessions isolated per page load if needed, 
                # or pass 'browser_context' if we want persistent session (better for pagination)
                click_selector=next_click_selector
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
            
            # 1. CARDS
            cards, winner = self._try_selectors(sel, rule.container_css)
            
            if not cards:
                 # Universal fallback for generic store structures
                 fallback_selectors = "li.catalog-products-list__item, li.simple-slider-list__item, li.product-item, .product-item, .product-card, .item, article"
                 cards, winner = self._try_selectors(sel, fallback_selectors)
                 if cards and winner:
                     logger.warning(f"🔧 [Auto-Fix] Switching container for {domain}: {rule.container_css} -> {winner}")
                     rule.container_css = winner
                     rule_updated = True

            if not cards:
                 logger.error(f"❌ Cards not found ({rule.container_css})")
                 break
                 
            logger.info(f"{rule.emoji} [Page {page_number}] Cards: {len(cards)}")

            try:
                for card in cards:
                    if processed_cards >= max_items: break
                    try:
                        # 2. TITLE
                        title_el, winner = self._try_selectors(card, rule.title_css)
                        title = self.extract_clean_text(title_el)
                        if not title:
                            fallback_title = ".product-details__name, .simple-slider-list__name, h3, h2, .title, a.title, .name"
                            title_el, winner = self._try_selectors(card, fallback_title)
                            title = self.extract_clean_text(title_el)
                            if title and winner:
                                rule.title_css = winner
                                rule_updated = True
                        
                        if not title: continue
                        
                        # 2.5 BRAND
                        brand = None
                        if rule.brand_css:
                            brand_el, _ = self._try_selectors(card, rule.brand_css)
                            brand = self.extract_clean_text(brand_el)

                        # 3. PRICE (Listing)
                        price_val = Decimal("0.00")
                        is_available = False
                        if rule.price_css:
                            price_el, winner = self._try_selectors(card, rule.price_css)
                            price_text = self.extract_clean_text(price_el)
                            price_val = self.parse_price(price_text)
                            is_available = True if price_val and price_val > Decimal("0") else False

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
                        if perform_deep_dive and rule.detail_trigger_text:
                            card_text = card.xpath('string(.)').get().lower()
                            keywords = [k.strip().lower() for k in rule.detail_trigger_text.split(',')]
                            # If NONE of the keywords are found, skip deep dive
                            if not any(k in card_text for k in keywords):
                                perform_deep_dive = False
                                logger.debug(f"⚡ Fast-track: No trigger '{rule.detail_trigger_text}' found. Skipping deep dive.")

                        if perform_deep_dive:
                            # --- SEQUENTIAL DEEP SCRAPING ---
                            # Fresh context for EVERY product to bypass session tracking
                            # Human delay between individual products
                            await asyncio.sleep(random.uniform(4.5, 8.5))
                            
                            logger.info(f"🔍 Deep dive (Fresh Start): {product_url}")
                            # PASS context=None to force fresh context
                            details = await self.scrape_product_details(product_url, rule, session=session, browser_context=None)
                            
                            from app.services.normalizer import perfume_normalizer
                            base_norm = perfume_normalizer.extract_all(title)
                            
                            for d in details:
                                full_title = f"{title} {d['title_suffix']}".strip()
                                v_norm = perfume_normalizer.extract_all(full_title)
                                
                                candidates.append({
                                    "url": product_url,
                                    "image_url": image_url,
                                    "brand": brand or v_norm["brand"] or base_norm["brand"],
                                    "volume": v_norm["volume"] or base_norm["volume"],
                                    "concentration": v_norm["concentration"] or base_norm["concentration"],
                                    "title": full_title,
                                    "price": d["price"],
                                    "is_available": d["is_available"]
                                })
                        else:
                            # Standard mode: process variants from card JSON if available
                            from app.services.normalizer import perfume_normalizer
                            norm = perfume_normalizer.extract_all(title)
                            listing_variants = self._extract_variants(card, norm["clean_name"])
                            if listing_variants:
                                for v in listing_variants:
                                    self._add_candidate(candidates, v["title"], v["price"], v["price"]>0, product_url, image_url, brand, norm)
                            else:
                                self._add_candidate(candidates, title, price_val, is_available, product_url, image_url, brand, norm)
                        
                        processed_cards += 1

                    except Exception as e:
                        logger.debug(f"Error parsing card: {e}")
                        continue
            finally:
                logger.debug("🚜 Finished processing catalog page.")
            
            # --- PAGINATION ---
            # --- PAGINATION (Hybrid: Link vs Click) ---
            next_page_link = None
            
            # 1. Try Rule-based selector
            if rule.next_page_css:
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
                await asyncio.sleep(random.uniform(2.0, 5.0))

            elif next_click_selector:
                # Case B: JS Click Navigation
                # current_url remains same (base), but action changes
                page_number += 1
                html = None
                
                logger.info(f"👆 Clicking to Page {page_number}...")
                await asyncio.sleep(random.uniform(2.0, 5.0))
                
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
        
        # --- PHASE 2: FILTERING AND ANALYSIS (Methods 1, 2, 3) ---
        valid_items = []
        
        if candidates:
            import json
            from app.services.validator import content_validator
            from datetime import datetime
            
            all_forbidden = []
            if intent:
                all_forbidden = intent.get("forbidden_keywords", []).copy()
            if rule.negative_keywords:
                try: 
                   context_negative = json.loads(rule.negative_keywords)
                   if isinstance(context_negative, list): all_forbidden.extend(context_negative)
                except: pass

            for item in candidates:
                # Check 2: Words (Method 2/3)
                if intent:
                    if content_validator.is_garbage(item["title"], all_forbidden):
                        # logger.debug(f"🗑️ [WordFilter] Drop {item['title']}")
                        continue
                    if not content_validator.check_brand(item["title"], intent.get("brand")):
                        continue
                
                valid_items.append(item)

        # --- PHASE 3: SAVING ---
        final_scraped_items = []
        # When variants are enabled, we should process up to max_items *original products*
        # But for simplicity, we'll just take the items from the final valid_items list.
        # To make sure we get what user expects, we should have limited cards earlier.
        
        logger.info(f"💾 Saving {len(valid_items)} items...")
        
        from app.services.matcher import matcher_service
        from app.domain.models import ProductGroup

        for item in valid_items:
            # 1. Check if product exists by URL + Volume (to support variants)
            stmt = select(Product).where(
                Product.url == item["url"],
                Product.volume == item["volume"]
            )
            product = (await session.execute(stmt)).scalar_one_or_none()
            
            # 2. Determine Group ID
            final_group_id = group_id
            
            if not final_group_id:
                # AUTO-MATCHING MODE (The Hardcore Part)
                # If product exists, keep its group.
                if product and product.group_id:
                    final_group_id = product.group_id
                else:
                    # Try to find a match by attributes
                    match = await matcher_service.find_best_match(session, item)
                    if match:
                        final_group_id = match.id
                    else:
                        # Create NEW Group (Chain)
                        canonical = matcher_service.get_canonical_name(item["title"])
                        new_group = ProductGroup(name=canonical, category="Perfume")
                        session.add(new_group)
                        await session.flush() # Get ID
                        final_group_id = new_group.id
                        logger.info(f"✨ Created NEW Chain: {new_group.name}")

            if not product:
                product = Product(
                    title=item["title"], 
                    url=item["url"], 
                    search_term=rule.site_name,
                    group_id=final_group_id,
                    brand=item.get("brand"),
                    volume=item.get("volume"),
                    concentration=item.get("concentration")
                )
                session.add(product)
                await session.flush()
                change_type = "initial"
            else:
                # Update group and attributes if they were missing
                if not product.group_id: product.group_id = final_group_id
                if not product.brand: product.brand = item.get("brand")
                if not product.volume: product.volume = item.get("volume")
                if not product.concentration: product.concentration = item.get("concentration")
                
                # Change Detection Logic
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
            
            # Ensure we don't save None to Decimal column if not allowed
            # but usually it's better to store 0.00 and is_available=False
            price_to_save = item["price"] if item["price"] is not None else Decimal("0.00")
            
            product.last_seen = datetime.utcnow()
            product.last_price = price_to_save
            product.is_available = item["is_available"]
            if item["image_url"]: product.image_url = item["image_url"]
            
            # Brand auto-discovery
            if not product.brand and item.get("title"):
                from app.services.normalizer import perfume_normalizer
                norm = perfume_normalizer.extract_all(item["title"])
                product.brand = norm.get("brand")

            session.add(product)

            # --- DIFF-SCRAPING: Only save history if something changed ---
            if change_type != "no_change":
                history = PriceHistory(
                    price=item["price"], 
                    in_stock=item["is_available"], 
                    product_id=product.id,
                    change_type=change_type
                )
                session.add(history)
                
                # Notify about SIGNIFICANT changes
                from app.services.notifier import notification_service
                notification_service.report_change(product, history, rule.site_name)
            else:
                pass # Silent update of last_seen/last_price only

            final_scraped_items.append(ScrapedItem(
                title=product.title, 
                price=item["price"], 
                availability="Yes", 
                url=product.url, 
                image_url=item["image_url"]
            ))

        await session.commit()        
        # --- QUALITY CONTROL & SELF-LEARNING ---
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

        return final_scraped_items


    def _add_candidate(self, candidates, title, price, is_available, url, image_url, brand, norm):
        """Standardizes and adds a product to the candidates list."""
        from app.services.normalizer import perfume_normalizer
        v_norm = perfume_normalizer.extract_all(title)
        
        candidates.append({
            "url": url,
            "image_url": image_url,
            "brand": brand or v_norm["brand"] or norm["brand"],
            "volume": v_norm["volume"] or norm["volume"],
            "concentration": v_norm["concentration"] or norm["concentration"],
            "title": title,
            "price": price,
            "is_available": is_available
        })

    async def scrape_page(self, url: str, rule: ScrapingRule = None, browser_context=None, click_selector: str = None):
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