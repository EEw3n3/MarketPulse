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

    def simplify_html(self, soup: BeautifulSoup) -> str:
        """
        Reduces token usage by removing repeated sibling elements (list items).
        Keeps structure but removes bulk.
        """
        for parent in soup.find_all(True):
            # Group children by tag name to identify lists
            children = [child for child in parent.find_all(recursive=False) if isinstance(child.name, str)]
            if len(children) > 10:
                # If we have many children of same tag (e.g. many LI or DIV), assume it's a list.
                # Keep first 5 and last 1 to show structure, remove middle.
                first_tag = children[0].name
                # varying classes might obscure similarity, but usually lists use same tag
                similar_children = [c for c in children if c.name == first_tag]
                
                if len(similar_children) > 10:
                    # Keep first 5 and last 1
                    # Add a marker saying items were removed
                    for child in similar_children[5:-1]:
                        child.decompose()
        
        return str(soup)

    def clean_html(self, html: str) -> str:
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # Remove non-visual or heavy tags
            for element in soup(["script", "style", "svg", "noscript", "meta", "link", "iframe", "head"]):
                element.decompose()
            
            # Remove comments
            from bs4 import Comment
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()

            # Smart reduction of repeated items
            return self.simplify_html(soup)[:50000] 
        except Exception as e: 
            logger.error(f"HTML Cleaning error: {e}")
            return html[:30000]

    async def generate_rule(self, session, url: str, html_content: str, error_hint: str = None) -> ScrapingRule:
        logger.info(f"🤖 Requesting AI help for: {url}...")
        
        clean_content = self.clean_html(html_content)
        
        # --- COLLECTIVE INTELLIGENCE ---
        stmt = select(SharedPattern).order_by(desc(SharedPattern.success_count)).limit(10)
        db_patterns = (await session.execute(stmt)).scalars().all()
        
        knowledge_base = ""
        if db_patterns:
            knowledge_base = "\nSuccessful patterns from other sites (try to match similar logic):\n"
            for p in db_patterns:
                knowledge_base += f"- {p.pattern_type}: {p.css_selector}\n"
        
        error_context = f"\nIMPORTANT: Your previous attempt failed: {error_hint}. Do NOT use the same selectors." if error_hint else ""
        
        prompt = f"""
        Act as a Senior Web Scraper.
        Target URL: {url}
        
        Task: Analyze the simplified HTML below and reverse-engineer the CSS selectors to scrape product data.
        
        CRITICAL RULES:
        1. **Stability**: Prefer `data-testid`, `id`, `itemprop` or meaningful class names (e.g. 'product-card', 'price') over random hashes (e.g. 'css-1x2y3z').
        2. **Container**: Find the REPEATING element that wraps a single product. It must appear multiple times.
        3. **Precision**: Title, Price, and Image selectors must be RELATIVE to the Container.
        4. **Anti-Noise**: Ignore "Recommended", "Recently Viewed", or "Cart" sidebars. Focus on the MAIN CATALOG GRID.
        
        {knowledge_base}
        {error_context}
        
        HTML SNIPPET (Simplified for brevity, repreated items removed):
        {clean_content}
        
        RETURN JSON:
        {{
            "site_name": "Store Name",
            "emoji": "🛒",
            "container_css": "distinct selector for the product card",
            "title_css": "selector for product name inside container",
            "price_css": "selector for price text inside container",
            "image_css": "selector for img tag inside container",
            "next_page_css": "selector for 'Next' button or pagination link",
            "negative_keywords": ["sponsored", "ad", "promo"]
        }}
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
