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

    async def scrape_catalog(self, session, start_url: str, initial_html: str = None, max_items: int = 100, group_id: Optional[int] = None, intent: dict = None, enable_price_filter: bool = True, site_name_ui: str = None):
        domain = urlparse(start_url).netloc.replace("www.", "")
        
        statement = select(ScrapingRule).where(ScrapingRule.domain == domain)
        result = await session.execute(statement)
        rule = result.scalar_one_or_none()
        if not rule: return []

        current_url = start_url
        candidates = [] 
        page_number = 1
        html = initial_html
        
        processed_cards = 0
        from app.services.ui import get_dashboard
        db = get_dashboard()

        while processed_cards < max_items and current_url:
            if not html:
                if db and site_name_ui:
                    db.update_status(site_name_ui, f"Loading Page {page_number}")
                
                html = await stealth_client.get_page(current_url)
                if not html:
                    try:
                        from app.core.browser import browser_manager
                        html = await browser_manager.get_page_content(current_url)
                    except: pass
            if not html: break 

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
                            logger.warning(f"🔧 Fixing title_css for {domain}: {rule.title_css} -> {winner}")
                            rule.title_css = winner
                            rule_updated = True
                    
                    if not title: continue

                    # 3. PRICE
                    price_val = Decimal("0.00")
                    if rule.price_css:
                        price_el, winner = self._try_selectors(card, rule.price_css)
                        if not price_el:
                            fallback_price = ".price_item, .simple-slider-list__price, .price b, .price, .product-price, .item-price, .val"
                            price_el, winner = self._try_selectors(card, fallback_price)
                            if price_el and winner:
                                logger.warning(f"🔧 Fixing price_css for {domain}: {rule.price_css} -> {winner}")
                                rule.price_css = winner
                                rule_updated = True
                        
                        price_text = self.extract_clean_text(price_el)
                        # SPECIAL CASE: Makeup.lv "Nav pieejams"
                        if any(x in price_text.lower() for x in ["pieejams", "available", "нету"]):
                            price_val = None
                            is_available = False
                        else:
                            price_val = self.parse_price(price_text)
                            # If price is 0 after parsing, it might be out of stock
                            is_available = True if price_val and price_val > Decimal("0") else False
                    else:
                        price_val = None
                        is_available = False

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
                    
                    # Store as primitive dict first for analysis
                    from app.services.normalizer import perfume_normalizer
                    norm = perfume_normalizer.extract_all(title)
                    
                    # --- VARIANT EXTRACTION (KILLER FEATURE) ---
                    found_variants = self._extract_variants(card, norm["clean_name"])
                    
                    base_payload = {
                        "url": product_url,
                        "image_url": image_url,
                        "brand": norm["brand"],
                        "volume": norm["volume"],
                        "concentration": norm["concentration"]
                    }

                    if found_variants:
                        for v in found_variants:
                            # Re-normalize variant title if needed or use base
                            v_norm = perfume_normalizer.extract_all(v["title"])
                            candidates.append({
                                **base_payload,
                                "title": v["title"],
                                "price": v["price"],
                                "url": f"{product_url}?variant={v['variant_id']}" if v.get("variant_id") else product_url,
                                "volume": v_norm["volume"] or norm["volume"],
                                "is_available": v["price"] > 0
                            })
                    else:
                         candidates.append({
                            **base_payload,
                            "title": title,
                            "price": price_val,
                            "is_available": is_available
                        })
                    
                    processed_cards += 1

                except Exception as e: 
                    logger.debug(f"Error parsing card: {e}")
                    continue
            
            # --- PAGINATION ---
            next_page = None

            def is_url_safe(href: str) -> bool:
                if not href: return False
                junk = ['/news/', '/product/', '/ads/', '/cart/']
                return not any(j in href.lower() for j in junk)

            if rule.next_page_css:
                el_p, winner = self._try_selectors(sel, rule.next_page_css)
                if el_p:
                    el = el_p[0]
                    attr = el.attrib.get('href') or el.css('a::attr(href)').get()
                    if attr:
                        candidate = urljoin(current_url, attr)
                        if is_url_safe(candidate):
                            next_page = candidate
                        else:
                            logger.warning(f"🚫 Rule suggested unsafe pagination: {candidate}. Falling back to smart logic.")
            
            if not next_page:
                next_page = self._find_next_page_fallback(sel, current_url)

            if rule_updated:
                session.add(rule)
            
            await session.commit()
            
            # --- UI UPDATE ---
            if db and site_name_ui:
                progress = min(100, int((len(candidates) / max_items) * 100))
                db.update_status(site_name_ui, f"Scanning (Found {len(candidates)} items)", progress)
                db.update_log(site_name_ui, f"Page {page_number}: Found {len(cards)} cards")

            if next_page and next_page != current_url and len(candidates) < max_items:
                current_url = next_page
                page_number += 1
                html = None 
                await asyncio.sleep(random.uniform(1.0, 2.5))
            else:
                logger.info("⏹️ Pagination finished (or limit reached).")
                if db and site_name_ui:
                    db.update_status(site_name_ui, "Finishing...", 100)
                break
        
        # --- PHASE 2: FILTERING AND ANALYSIS (Methods 1, 2, 3) ---
        valid_items = []
        
        if candidates:
            # 1. Price Anomaly Detection (Method 1)
            # Find the most expensive items to establish a baseline
            all_prices = [c["price"] for c in candidates if c["price"] > 0]
            max_price = max(all_prices) if all_prices else Decimal("0.00")
            
            # If item is over 50 euro, consider everything cheaper than 10% as accessories
            # Using 10% as threshold. If phone is 1000, everything below 100 is garbage.
            price_threshold = Decimal("0.00")
            if enable_price_filter and max_price > Decimal("50.00"):
                price_threshold = max_price * Decimal("0.10")
                logger.info(f"💰 [PriceFilter] Max: {max_price}€ | Threshold: {price_threshold}€ (Dropping cheaper items)")

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
                # Check 1: Price (Method 1)
                if item["price"] < price_threshold and item["price"] > 0:
                     logger.debug(f"📉 [PriceFilter] Drop {item['title']} ({item['price']}€ < {price_threshold}€)")
                     continue
                
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
            # 1. Check if product exists by URL
            stmt = select(Product).where(Product.url == item["url"])
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
            
            product.last_price = price_to_save
            product.is_available = item["is_available"]
            if item["image_url"]: product.image_url = item["image_url"]
            
            # Brand auto-discovery: if normalizer failed, but we have a title
            if not product.brand and item.get("title"):
                from app.services.normalizer import perfume_normalizer
                norm = perfume_normalizer.extract_all(item["title"])
                product.brand = norm.get("brand")

            session.add(product)

            history = PriceHistory(
                price=item["price"], 
                in_stock=item["is_available"], 
                product_id=product.id,
                change_type=change_type
            )
            session.add(history)
            
            # 4. Notify about changes
            from app.services.notifier import notification_service
            notification_service.report_change(product, history, rule.site_name)
            
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


    async def scrape_page(self, url: str):
        html = await stealth_client.get_page(url)
        return {"html": html} if html else None

    async def close(self):
        if 'app.core.browser' in sys.modules:
             from app.core.browser import browser_manager
             await browser_manager.stop()

scraper_service = ScraperService()