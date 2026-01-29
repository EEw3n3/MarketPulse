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
            logger.warning(f"♻️ Deleting old rule for {domain}...")
            await session.delete(rule)
            await session.commit()
            rule = None
        
        if rule:
            logger.info(f"📍 Found rule for {domain}")
            return rule
            
        new_rule = await self.generate_rule(session, url, html_content, error_hint=error_hint)

        
        if new_rule:
            new_rule.domain = domain 
            session.add(new_rule)
            await session.commit()
            await session.refresh(new_rule)
            logger.success(f"💾 New rule for {domain} saved.")
            return new_rule
            
        return None

    def clean_html(self, html: str) -> str:
        try:
            soup = BeautifulSoup(html, "html.parser")
            useless_tags = ["script", "style", "svg", "path", "noscript", "meta", "link", "iframe", "header", "footer"]
            for element in soup(useless_tags): element.decompose()
            
            # AGGRESSIVE CLEANING: Remove only obvious non-content blocks
            junk_markers = ["banner", "sidebar", "footer", "popup", "menu", "nav", "widget"]
            for element in soup.find_all(True):
                class_str = " ".join(element.get("class", [])).lower()
                id_str = element.get("id", "").lower()
                if any(marker in class_str or marker in id_str for marker in junk_markers):
                    element.decompose()

            # Removing empty elements to save tokens
            for element in soup.find_all():
                if len(element.get_text(strip=True)) == 0 and not element.find_all(): element.decompose()
            return str(soup)[:60000]
        except Exception: return html[:30000]

    async def generate_rule(self, session, url: str, html_content: str, error_hint: str = None) -> ScrapingRule:
        logger.info(f"🤖 Requesting AI help for: {url}...")
        if error_hint:
             logger.warning(f"💡 Using error hint: {error_hint}")

        clean_content = self.clean_html(html_content)
        
        # --- COLLECTIVE INTELLIGENCE: Retrieving best patterns ---
        stmt = select(SharedPattern).order_by(desc(SharedPattern.success_count)).limit(15)
        db_patterns = (await session.execute(stmt)).scalars().all()
        
        knowledge_base = ""
        if db_patterns:
            knowledge_base = "\nKNOWLEDGE BASE (Patterns that often work):\n"
            for p in db_patterns:
                knowledge_base += f"- {p.pattern_type}: {p.css_selector} (Success count: {p.success_count})\n"
        
        hint_text = f"\nCRITICAL: Previous attempt failed with error: {error_hint}. AVOID the selectors that caused this!" if error_hint else ""
        
        # Prompt is now absolutely universal
        prompt = f"""
        Analyze the HTML from: {url}
        Task: Identify CSS selectors for a product catalog.
        {hint_text}
        {knowledge_base}
        
        INSTRUCTION:
        1. Look at the HTML snippet and find the container that holds the LARGEST number of products (this is the main catalog).
        2. Note: The main catalog might contain special "sponsored" items or internal sliders - include them if they are part of the main grid.
        3. AVOID selecting small "You might also like" or "Recently viewed" blocks usually found at the bottom or sides.
        4. Choose the container CSS that captures all products in the main results list.
        4. Check if any patterns from the KNOWLEDGE BASE match the actual product list structure. Use them if they fit!
        5. If no patterns match, find NEW precise selectors.
        
        RETURN JSON OBJECT:
        - "site_name": Store name.
        - "emoji": Store icon.
        - "container_css": CSS selector for product card (e.g. 'li.catalog-item'). MUST be the main catalog list.
        - "title_css": CSS selector for Title, relative to container.
        - "price_css": CSS selector for Price, relative to container.
        - "image_css": CSS selector for Product Image (usually img tag or its container).
        - "next_page_css": CSS selector for Next page button or link.
        - "negative_keywords": LIST of strings (junk words).
        
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
            logger.success(f"🤖 AI generated: {data}")
            
            if not data.get("container_css") or not data.get("title_css"): return None
            
            return ScrapingRule(
                domain=urlparse(url).netloc.replace("www.", ""),
                site_name=data.get("site_name", "Unknown"),
                emoji=data.get("emoji", "🛒"),
                container_css=data.get("container_css"),
                title_css=data.get("title_css"),
                price_css=data.get("price_css"),
                image_css=data.get("image_css"),
                next_page_css=data.get("next_page_css"),
                negative_keywords=json.dumps(data.get("negative_keywords", []))
            )
        except Exception as e:
            logger.error(f"AI error: {e}")
            return None

ai_generator = AIGenerator()
