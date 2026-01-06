import json
from urllib.parse import urlparse
from openai import AsyncOpenAI
from bs4 import BeautifulSoup
from loguru import logger
from sqlmodel import select
from app.core.config import settings
from app.domain.models import ScrapingRule

class AIGenerator:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def get_or_create_rule(self, session, url: str, html_content: str, force_refresh: bool = False) -> ScrapingRule:
        domain = urlparse(url).netloc.replace("www.", "")
        
        statement = select(ScrapingRule).where(ScrapingRule.domain == domain)
        result = await session.execute(statement)
        rule = result.scalar_one_or_none()
        
        if rule and force_refresh:
            logger.warning(f"♻️ Удаляю старое правило для {domain}...")
            await session.delete(rule)
            await session.commit()
            rule = None
        
        if rule:
            logger.info(f"📍 Найдено правило для {domain}")
            return rule
            
        new_rule = await self.generate_rule(url, html_content)
        
        if new_rule:
            new_rule.domain = domain 
            session.add(new_rule)
            await session.commit()
            await session.refresh(new_rule)
            logger.success(f"💾 Новое правило для {domain} сохранено.")
            return new_rule
            
        return None

    def clean_html(self, html: str) -> str:
        try:
            soup = BeautifulSoup(html, "html.parser")
            useless_tags = ["script", "style", "svg", "path", "noscript", "meta", "link", "iframe"]
            for element in soup(useless_tags): element.decompose()
            # Удаляем пустые элементы для экономии токенов
            for element in soup.find_all():
                if len(element.get_text(strip=True)) == 0 and not element.find_all(): element.decompose()
            return str(soup)[:60000]
        except Exception: return html[:30000]

    async def generate_rule(self, url: str, html_content: str) -> ScrapingRule:
        logger.info(f"🤖 Запрашиваю помощь ИИ для: {url}...")
        clean_content = self.clean_html(html_content)
        
        # Промпт теперь абсолютно универсален
        prompt = f"""
        Analyze the HTML from: {url}
        Task: Identify CSS selectors for a product catalog.
        
        RETURN JSON OBJECT:
        - "site_name": Store name.
        - "emoji": Store icon.
        - "container_css": CSS selector for the product card wrapper. Provide 2-3 common variations comma-separated (e.g. 'li.item, div.card').
        - "title_css": CSS selector for the product Title.
        - "price_css": CSS selector for the Price.
        - "next_page_css": CSS selector for the 'Next Page' button/link.
        
        RULES:
        1. Be precise with tag names (li, div, article).
        2. Avoid guessing parent classes that are not strictly necessary (prefer '.product' over 'div.catalog ul.products li.product').
        3. For 'container_css', prioritize the tag that is repeated for each product.
        4. For 'price_css', look for tags containing numbers and currency symbols.
        
        HTML SNIPPET:
        {clean_content}
        """

        try:
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            data = json.loads(response.choices[0].message.content)
            logger.success(f"🤖 ИИ сгенерировал: {data}")
            
            if not data.get("container_css") or not data.get("title_css"): return None
            
            return ScrapingRule(
                domain=urlparse(url).netloc.replace("www.", ""),
                site_name=data.get("site_name", "Unknown"),
                emoji=data.get("emoji", "🛒"),
                container_css=data.get("container_css"),
                title_css=data.get("title_css"),
                price_css=data.get("price_css"),
                next_page_css=data.get("next_page_css")
            )
        except Exception as e:
            logger.error(f"Ошибка AI: {e}")
            return None

ai_generator = AIGenerator()