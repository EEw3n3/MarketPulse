import json
from urllib.parse import urlparse
from openai import AsyncOpenAI
from bs4 import BeautifulSoup
from loguru import logger
from sqlmodel import select, desc
from app.core.config import settings
from app.domain.models import ScrapingRule, SharedPattern

class AIGenerator:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def get_or_create_rule(self, session, url: str, html_content: str, force_refresh: bool = False, error_hint: str = None) -> ScrapingRule:

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
            
        new_rule = await self.generate_rule(session, url, html_content, error_hint=error_hint)

        
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

    async def generate_rule(self, session, url: str, html_content: str, error_hint: str = None) -> ScrapingRule:
        logger.info(f"🤖 Запрашиваю помощь ИИ для: {url}...")
        if error_hint:
             logger.warning(f"💡 Использую подсказку об ошибке: {error_hint}")

        clean_content = self.clean_html(html_content)
        
        # --- КОЛЛЕКТИВНЫЙ РАЗУМ: Достаем лучшие паттерны ---
        stmt = select(SharedPattern).order_by(desc(SharedPattern.success_count)).limit(10)
        db_patterns = (await session.execute(stmt)).scalars().all()
        
        knowledge_base = ""
        if db_patterns:
            knowledge_base = "\nKNOWLEDGE BASE (Patterns that often work):\n"
            for p in db_patterns:
                knowledge_base += f"- {p.pattern_type}: {p.css_selector} (Success count: {p.success_count})\n"
        
        hint_text = f"\nCRITICAL: Previous attempt failed with error: {error_hint}. AVOID the selectors that caused this!" if error_hint else ""
        
        # Промпт теперь абсолютно универсален
        prompt = f"""
        Analyze the HTML from: {url}
        Task: Identify CSS selectors for a product catalog.
        {hint_text}
        {knowledge_base}
        
        INSTRUCTION:
        1. Look at the HTML snippet.
        2. Check if any patterns from the KNOWLEDGE BASE match the structure. Use them if they fit!
        3. If no patterns match, find NEW precise selectors.
        
        RETURN JSON OBJECT:
        - "site_name": Store name.
        - "emoji": Store icon.
        - "container_css": CSS selector for product card (e.g. 'li.item').
        - "title_css": CSS selector for Title.
        - "price_css": CSS selector for Price.
        - "next_page_css": CSS selector for Next page.
        
        HTML SNIPPET:
        {clean_content}
        """

        try:
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "system", "content": "You are a professional web scraping expert."}, 
                          {"role": "user", "content": prompt}],
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
