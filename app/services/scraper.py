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
        # Удаляем валюты, пробелы, неразрывные пробелы
        clean = re.sub(r'[^\d.,]', '', price_text)
        clean = clean.replace(',', '.')
        if clean.count('.') > 1: clean = clean.replace('.', '', clean.count('.') - 1)
        try: return Decimal(clean)
        except: return Decimal("0.00")

    def extract_clean_text(self, element: Selector) -> str:
        if not element: return ""
        return element.xpath('string(.)').get().strip()

    def validate_dataset(self, items: list[ScrapedItem]) -> dict:
        """
        Проверяет качество собранных данных. 
        Возвращает отчет о 'здоровье' сета.
        """
        if not items:
            return {"score": 0.0, "error": "No items found", "is_healthy": False}

        total = len(items)
        zero_prices = sum(1 for i in items if i.price <= 0)
        short_titles = sum(1 for i in items if len(i.title) < 5)
        
        # Штрафные баллы
        penalty = (zero_prices / total) * 0.7  # Цены важнее всего
        penalty += (short_titles / total) * 0.3 # Заголовки тоже важны
        
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
        Сохраняет удачные селекторы в общую базу знаний.
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
            
            # Ищем, есть ли уже такой паттерн
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
        logger.info(f"🧠 Паттерны сайта {rule.domain} добавлены в базу знаний.")


    def _find_next_page_fallback(self, sel: Selector, current_url: str) -> str | None:
        def clean_href(href: str | None) -> str | None:
            if not href: return None
            if href.startswith('javascript:') or href == '#': return None
            
            # Если ссылка уже абсолютная - берем как есть
            if bool(urlparse(href).netloc):
                return href
                
            # Иначе соединяем с корнем домена или текущей страницей
            parsed_base = urlparse(current_url)
            base_root = f"{parsed_base.scheme}://{parsed_base.netloc}"
            
            if href.startswith('/'):
                return urljoin(base_root, href)
            else:
                return urljoin(current_url, href)

        # 1. Standard rel="next"
        link = sel.css('link[rel="next"]::attr(href), a[rel="next"]::attr(href)').get()
        if clean_href(link): return clean_href(link)
        
        # 2. Text markers
        next_markers = ['>', '»', 'Next', 'next', 'Next page', 'Siguiente', 'Dalje', 'Nākamā']
        for marker in next_markers:
            link = sel.xpath(f"//a[contains(text(), '{marker}')]/@href").get()
            if clean_href(link): return clean_href(link)

        # 3. Numeric pagination
        active_candidates = ['is-active', 'active', 'current', 'selected', 'active-page']
        for cls in active_candidates:
            xpath_query = f"//*[contains(@class, '{cls}')]/following-sibling::a/@href"
            links = sel.xpath(xpath_query).getall()
            for l in links:
                if clean_href(l): return clean_href(l)
            
            xpath_li = f"//li[contains(@class, '{cls}')]/following-sibling::li/a/@href"
            links_li = sel.xpath(xpath_li).getall()
            for l in links_li:
                if clean_href(l): return clean_href(l)
        
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

    async def scrape_catalog(self, session, start_url: str, initial_html: str = None, max_items: int = 100, group_id: Optional[int] = None, intent: dict = None):
        domain = urlparse(start_url).netloc.replace("www.", "")
        
        statement = select(ScrapingRule).where(ScrapingRule.domain == domain)
        result = await session.execute(statement)
        rule = result.scalar_one_or_none()
        if not rule: return []

        current_url = start_url
        candidates = [] 
        page_number = 1
        html = initial_html
        
        # --- ФАЗА 1: СБОР КАНДИДАТОВ ---
        while len(candidates) < max_items * 2 and current_url: # Собираем с запасом
            if not html:
                logger.info(f"🚀 [Page {page_number}] Загрузка: {current_url}")
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
                 fallback_selectors = "li.product, li.product-item, .product-item, .item, article"
                 cards, winner = self._try_selectors(sel, fallback_selectors)
                 if cards and winner:
                     logger.warning(f"🔧 Исправляю container_css для {domain}: {rule.container_css} -> {winner}")
                     rule.container_css = winner
                     rule_updated = True

            if not cards:
                 logger.error(f"❌ Карточки не найдены ({rule.container_css})")
                 break
                 
            logger.info(f"{rule.emoji} [Page {page_number}] Карточек: {len(cards)}")

            for card in cards:
                if len(candidates) >= max_items * 3: break
                try:
                    # 2. TITLE
                    title_el, winner = self._try_selectors(card, rule.title_css)
                    title = self.extract_clean_text(title_el)
                    if not title:
                        fallback_title = "h3, h2, .title, a.title, .name"
                        title_el, winner = self._try_selectors(card, fallback_title)
                        title = self.extract_clean_text(title_el)
                        if title and winner:
                            logger.warning(f"🔧 Исправляю title_css для {domain}: {rule.title_css} -> {winner}")
                            rule.title_css = winner
                            rule_updated = True
                    
                    if not title: continue

                    # 3. PRICE
                    price_val = Decimal("0.00")
                    if rule.price_css:
                        price_el, winner = self._try_selectors(card, rule.price_css)
                        if not price_el:
                            fallback_price = ".price b, .price, .product-price, .item-price, .val"
                            price_el, winner = self._try_selectors(card, fallback_price)
                            if price_el and winner:
                                logger.warning(f"🔧 Исправляю price_css для {domain}: {rule.price_css} -> {winner}")
                                rule.price_css = winner
                                rule_updated = True
                        
                        price_text = self.extract_clean_text(price_el)
                        price_val = self.parse_price(price_text)

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

                    if not link_node: link_node = card.css("*::attr(href)").get()
                    if link_node: product_url = urljoin(current_url, link_node)
                    
                    # Store as primitive dict first for analysis
                    candidates.append({
                        "title": title,
                        "price": price_val,
                        "url": product_url,
                        "image_url": image_url
                    })

                except Exception: continue
            
            # --- ПАГИНАЦИЯ ---
            next_page = None
            if rule.next_page_css:
                el_p, winner = self._try_selectors(sel, rule.next_page_css)
                if el_p:
                    el = el_p[0]
                    attr = el.attrib.get('href') or el.css('a::attr(href)').get()
                    if attr: next_page = urljoin(current_url, attr)
            
            if not next_page:
                next_page = self._find_next_page_fallback(sel, current_url)

            if rule_updated:
                session.add(rule)
            
            await session.commit()

            if next_page and next_page != current_url and len(candidates) < max_items:
                logger.info(f"➡️ Переход на следующую страницу: {next_page}")
                current_url = next_page
                page_number += 1
                html = None 
                await asyncio.sleep(random.uniform(1.0, 2.5))
            else:
                logger.info("⏹️ Пагинация завершена (или лимит достигнут).")
                break
        
        # --- ФАЗА 2: ФИЛЬТРАЦИЯ И АНАЛИЗ (Методы 1, 2, 3) ---
        valid_items = []
        
        if candidates:
            # 1. Price Anomaly Detection (Метод 1)
            # Find the most expensive items to establish a baseline
            all_prices = [c["price"] for c in candidates if c["price"] > 0]
            max_price = max(all_prices) if all_prices else Decimal("0.00")
            
            # Если цена очень низкая в принципе, фильтр не нужен
            price_threshold = Decimal("0.00")
            if max_price > Decimal("50.00"):
                # Если товар дороже 50 евро, считаем, что все, что дешевле 10% от него - это аксессуары
                # Используем 10% как порог. Если телефон 1000, все что ниже 100 - мусор.
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
                # Чек 1: Цена (Метод 1)
                if item["price"] < price_threshold and item["price"] > 0:
                     logger.debug(f"📉 [PriceFilter] Drop {item['title']} ({item['price']}€ < {price_threshold}€)")
                     continue
                
                # Чек 2: Слова (Метод 2/3)
                if intent:
                    if content_validator.is_garbage(item["title"], all_forbidden):
                        # logger.debug(f"🗑️ [WordFilter] Drop {item['title']}")
                        continue
                    if not content_validator.check_brand(item["title"], intent.get("brand")):
                        continue
                
                valid_items.append(item)

        # --- ФАЗА 3: СОХРАНЕНИЕ ---
        final_scraped_items = []
        logger.info(f"💾 Сохранение {len(valid_items)} товаров (из {len(candidates)} кандидатов)...")
        
        for item in valid_items[:max_items]:
            stmt = select(Product).where(Product.url == item["url"])
            product = (await session.execute(stmt)).scalar_one_or_none()
            
            if not product:
                product = Product(
                    title=item["title"], 
                    url=item["url"], 
                    search_term=rule.site_name,
                    group_id=group_id
                )
                session.add(product)
                await session.flush()
            
            product.last_price = item["price"]
            if item["image_url"]: product.image_url = item["image_url"]
            session.add(product)

            history = PriceHistory(price=item["price"], in_stock=True, product_id=product.id)
            session.add(history)
            
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
            logger.success(f"💎 Качество данных подтверждено: {report['score']} ({len(final_scraped_items)} шт)")
            await self.learn_from_success(session, rule)
        else:
            rule.failure_count += 1
            rule.last_error = report.get("error", "Unknown error")
            logger.warning(f"💊 Низкое качество данных: {report['score']} | Ошибка: {rule.last_error}")

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