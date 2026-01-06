import asyncio
import random
import sys
import re
from dataclasses import dataclass
from decimal import Decimal
from parsel import Selector
from loguru import logger
from sqlmodel import select
from urllib.parse import urljoin, urlparse

from app.domain.models import ScrapingRule, Product, PriceHistory
from app.core.client import stealth_client

@dataclass
class ScrapedItem:
    title: str
    price: Decimal
    availability: str
    url: str

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

    def _find_next_page_fallback(self, sel: Selector, current_url: str) -> str | None:
        def clean_href(href: str | None) -> str | None:
            if not href: return None
            if href.startswith('javascript:') or href == '#': return None
            
            # РЕШЕНИЕ ПРОБЛЕМЫ "Фрактальных URL":
            # Если href начинается с 'categories/' (как на rdveikals), 
            # он скорее всего коренной, а не относительный к текущей папке.
            if href.startswith('categories/') or href.startswith('catalog/'):
                parsed = urlparse(current_url)
                joined = urljoin(f"{parsed.scheme}://{parsed.netloc}/", href)
            else:
                joined = urljoin(current_url, href)
            
            return joined

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
            # Ищем всех соседей-ссылок и перебираем их
            xpath_query = f"//*[contains(@class, '{cls}')]/following-sibling::a/@href"
            links = sel.xpath(xpath_query).getall()
            for l in links:
                if clean_href(l): return clean_href(l)
            
            # Пробуем через родителя (li)
            xpath_li = f"//li[contains(@class, '{cls}')]/following-sibling::li/a/@href"
            links_li = sel.xpath(xpath_li).getall()
            for l in links_li:
                if clean_href(l): return clean_href(l)
        
        # 4. Последний шанс: любая ссылка в блоке пагинации, которая больше текущей страницы
        # (Оставим это как идею, если не сработает выше)

        return None

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

    async def scrape_catalog(self, session, start_url: str, initial_html: str = None, max_items: int = 100):
        domain = urlparse(start_url).netloc.replace("www.", "")
        
        statement = select(ScrapingRule).where(ScrapingRule.domain == domain)
        result = await session.execute(statement)
        rule = result.scalar_one_or_none()
        if not rule: return []

        current_url = start_url
        collected_items = []
        page_number = 1
        html = initial_html
        
        while len(collected_items) < max_items and current_url:
            if not html:
                logger.info(f"🚀 [Page {page_number}] Загрузка: {current_url}")
                html = await stealth_client.get_page(current_url)
                if not html:
                    from app.core.browser import browser_manager
                    html = await browser_manager.get_page_content(current_url)
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
                if len(collected_items) >= max_items: break
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

                    # 4. URL
                    product_url = current_url
                    link_node = card.css("a::attr(href)").get()
                    if not link_node: link_node = card.css("*::attr(href)").get()
                    if link_node: product_url = urljoin(current_url, link_node)

                    stmt = select(Product).where(Product.url == product_url)
                    product = (await session.execute(stmt)).scalar_one_or_none()
                    
                    if not product:
                        product = Product(title=title, url=product_url, search_term=rule.site_name)
                        session.add(product)
                        await session.flush()
                    
                    history = PriceHistory(price=price_val, in_stock=True, product_id=product.id)
                    session.add(history)
                    
                    collected_items.append(ScrapedItem(title=product.title, price=price_val, availability="Yes", url=product.url))
                    
                except Exception: continue
            
            # --- ПАГИНАЦИЯ ---
            next_page = None
            if rule.next_page_css:
                el_p, winner = self._try_selectors(sel, rule.next_page_css)
                if el_p:
                    el = el_p[0] # Берем первый найденный элемент
                    attr = el.attrib.get('href') or el.css('a::attr(href)').get()
                    if attr: next_page = urljoin(current_url, attr)
            
            if not next_page:
                next_page = self._find_next_page_fallback(sel, current_url)

            if rule_updated:
                session.add(rule)
            
            await session.commit()

            if next_page and next_page != current_url:
                logger.info(f"➡️ Переход на следующую страницу: {next_page}")
                current_url = next_page
                page_number += 1
                html = None 
                await asyncio.sleep(random.uniform(1.0, 2.5))
            else:
                logger.info("⏹️ Пагинация завершена.")
                break
        
        return collected_items

    async def scrape_page(self, url: str):
        html = await stealth_client.get_page(url)
        return {"html": html} if html else None

    async def close(self):
        if 'app.core.browser' in sys.modules:
             from app.core.browser import browser_manager
             await browser_manager.stop()

scraper_service = ScraperService()