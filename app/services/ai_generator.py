import json
from urllib.parse import urlparse
from typing import Optional
# from openai import AsyncOpenAI
from google import genai
from google.genai import types
from bs4 import BeautifulSoup
from parsel import Selector
from loguru import logger
from sqlmodel import select, desc
from app.core.config import settings
from app.domain.models import ScrapingRule, SharedPattern

class AIGenerator:
    def __init__(self):
        # self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.client = genai.Client(api_key=settings.GOOGLE_API_KEY)

    async def get_or_create_rule(self, session, url: str, html_content: str, force_refresh: bool = False, error_hint: Optional[str] = None) -> Optional[ScrapingRule]:

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

        # --- VERIFIED FAST-PATH: Skip AI entirely for known domains ---
        # These selectors are ground-truth confirmed by manual HTML inspection.
        # Checking FIRST avoids wasting 3×15s = 45s on AI calls that get overridden anyway.
        VERIFIED_DETAIL_RULES = {
            # Verified 2026-04-17 by HTML reverse-engineering (lab/debug_notino_lv.html)
            # NOTE: class-based selectors (styled__*) change on every Notino deploy.
            # Using data-testid attributes which are stable across deployments.
            "notino.lv": {
                "site_name": "Notino",
                "emoji": "👃",
                "container_css": "[data-testid='product-container']:not([data-recommendation='promo-banner'])",
                # Notino renders two component variants: ProductCard (Playwright) vs ProductTile (real browser).
                # Both selectors provided as comma-fallback for _try_selectors.
                "title_css": "[data-testid='product-card-name'], [data-testid='product-tile-name']",
                "brand_css": "[data-testid='product-card-brand'], [data-testid='product-tile-brand']",
                "price_css": "[data-testid='price-component']",
                "image_css": "img[loading='lazy']",
                "next_page_css": ".nextPage[data-testid='page-button-wrapper']",
                "use_detail_page": True,
                "detail_trigger_text": "sākot ar,no ",
            },
            # Verified 2026-04-17 by HTML reverse-engineering (lab/debug_douglas_lv.html)
            # Douglas Latvia changed HTML structure: old .product-tile → new .product_element
            # Price is in span.now (can contain "Šobrīd nav"/"Drīz tirdzniecībā!" for OOS)
            # Tealium JSON (data-tealium-info) available for deep dive variant extraction
            "douglas.lv": {
                "site_name": "Douglas Latvia",
                "emoji": "💄",
                "container_css": "div.product_element",
                "title_css": "span.name",
                "brand_css": "span.brand_caps",
                "price_css": "span.price span.now",
                # Catalog card concentration element ("Parfimērijas ūdens …",
                # "Tualetes ūdens …"); detail page uses span.product_type as
                # fallback — both match the same CONC_MAP keys.
                "concentration_css": "span.type, span.product_type",
                "image_css": "img.product-photo",
                "next_page_css": "a.page.next",
                "use_detail_page": True,
                "detail_trigger_text": "no ,sākot",
                "detail_variant_selector": "fieldset.items div.item",
                "detail_variant_name_css": "span.name",
                "detail_variant_price_css": "div.price span.now",
            },
            # Verified 2026-03-15 by HTML reverse-engineering (scout_220.py)
            # SPA (Pigu platform) -- products loaded by browser JS, parsed via widget-data JSON
            # Price extraction done via _extract_220_from_widget_data() in scraper.py
            "220.lv": {
                "site_name": "220.lv",
                "emoji": "⚡",
                "container_css": "div.c-product-card",
                "title_css": ".c-product-card__title a",
                "price_css": ".c-price:not(.h-price--loyalty)",  # fallback only; widget-data preferred
                "image_css": "img.c-product-card__image",
                "next_page_css": "[class*=pagination] a:last-child",
            },
            # Verified 2026-10-08 on the live page (Ervin, DevTools). Cards are
            # rendered client-side by LupaSearch; parsed by _extract_1a_cards()
            # in scraper.py, these selectors are the DOM fallback. The old
            # catalog-taxons-product markup (2026-03) no longer exists.
            # price_css = regular price; the SMART NET loyalty price is
            # .special-price .catalog-taxons-product-price__price-number.
            # Pagination: ?page=N (URL-pattern fallback in scraper.py).
            "1a.lv": {
                "site_name": "1a.lv",
                "emoji": "🛒",
                "container_css": "div.lupa-search-result-product-card",
                "title_css": "a.lupa-title-link",
                "price_css": ".catalog-taxons-product__price .catalog-taxons-product-price__item-price",
                "image_css": "img.lupa-search-results-image",
                "next_page_css": None,
            }
        }

        if domain in VERIFIED_DETAIL_RULES:
            # Skip AI — build rule directly from verified selectors
            logger.info(f"⚡ VERIFIED fast-path for {domain} — skipping AI generation")
            override = VERIFIED_DETAIL_RULES[domain]
            
            # Atomic check-and-create to avoid IntegrityError
            stmt = select(ScrapingRule).where(ScrapingRule.domain == domain)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            
            if existing:
                for field, value in override.items():
                    setattr(existing, field, value)
                new_rule = existing
            else:
                new_rule = ScrapingRule(domain=domain)
                for field, value in override.items():
                    setattr(new_rule, field, value)
            
            session.add(new_rule)
            await session.commit()
            await session.refresh(new_rule)
            logger.success(f"🔩 VERIFIED rule created/updated instantly for {domain}")
            return new_rule

        new_rule = await self.generate_rule(session, url, html_content, error_hint=error_hint)

        # --- VALIDATION LOOP: Ensure rule finds multiple items (Catalog) ---
        if new_rule:
            sel = Selector(text=html_content)
            cards_found = len(sel.css(new_rule.container_css))

            attempts = 1
            max_attempts = 3
            while cards_found < 5 and attempts < max_attempts:
                logger.warning(f"⚠️ Rule for {domain} only found {cards_found} items. Retrying AI...")
                attempts += 1
                hint = f"Your previous container_css '{new_rule.container_css}' only found {cards_found} items. I need a selector for the main product grid (usually 10-50 items)."
                new_rule = await self.generate_rule(session, url, html_content, error_hint=hint)
                if not new_rule: break
                cards_found = len(sel.css(new_rule.container_css))

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

    def clean_html(self, html: str, limit: int = 0) -> str:
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # Remove non-visual or heavy tags
            for element in soup(["script", "style", "svg", "noscript", "meta", "link", "iframe", "head"]):
                element.decompose()
            
            # Remove comments
            from bs4 import Comment
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()

            cleaned = self.simplify_html(soup)
            
            # If explicit limit is set (e.g. for Detail Page), use straightforward truncation
            if limit > 0:
                if len(cleaned) > limit:
                    logger.warning(f"⚠️ Truncating Detail HTML from {len(cleaned)} to {limit}")
                    return cleaned[:limit]
            
            # SMART TRUNCATION FOR CATALOGS
            # We need the TOP (headers, first items) and the BOTTOM (pagination).
            # The middle is repetitive product cards, so we can cut it safely.
            MAX_TOTAL = 150000
            if len(cleaned) > MAX_TOTAL:
                keep_size = MAX_TOTAL // 2
                head = cleaned[:keep_size]
                tail = cleaned[-keep_size:]
                logger.info(f"✂️ Smart Truncation: Keeping first {keep_size} and last {keep_size} chars. Dropped middle.")
                return head + "\n... [MIDDLE CONTENT REMOVED] ...\n" + tail
            
            return cleaned
            
        except Exception as e: 
            logger.error(f"HTML Cleaning error: {e}")
            return html[:30000]

    async def generate_rule(self, session, url: str, html_content: str, error_hint: str = None) -> ScrapingRule:
        logger.info(f"🤖 Requesting AI help for: {url}...")
        
        # Use smart cleaning
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
        2. **Container**: Find the REPEATING element that wraps a single product in the MAIN catalog grid. It must appear multiple times (usually 10-50 times).
        3. **Precision**: Title, Price, and Image selectors must be RELATIVE to the Container.
        4. **Anti-Noise**: IGNORE single items, "Recommended" blocks, "Recently Viewed" carousels, or "Cart" sidebars. They often have different structures. Focus ONLY on the primary product grid.
        5. **Variants**: Check if price has a prefix like "sākot no", "from", "ab". This indicates multiple options. Return this keyword.
        
        PAGINATION STRATEGY (CRITICAL):
        - Find the 'Next Page' button or link.
        - Look for `rel="next"`, `aria-label="Next"`, `aria-label="Nākamā"`.
        - Look for text like "Next", ">", "»", "Nākamā".
        - Ensure it is a CLICKABLE element (a tag or button).
        - NOT the disabled button.
        
        {knowledge_base}
        {error_context}
        
        HTML SNIPPET (Smartly truncated - Head and Tail preserved):
        {clean_content}
        
        RETURN JSON:
        {{
            "site_name": "Store Name",
            "emoji": "🛒",
            "container_css": "distinct selector for the product card",
            "title_css": "selector for product name inside container",
            "brand_css": "selector for brand name inside container (often above title)",
            "price_css": "selector for price text inside container",
            "concentration_css": "selector for a dedicated element holding perfume concentration type (e.g. 'Tualetes ūdens', 'Parfimērijas ūdens', 'Eau de Parfum'). Return null if no such standalone element exists — the concentration often lives inline in the title and will be parsed from there.",
            "image_css": "selector for img tag inside container",
            "next_page_css": "robust selector for 'Next' button",
            "detail_trigger_text": "text pattern that indicates multiple variants (e.g. 'sākot', 'from'). If none, null.",
            "negative_keywords": ["sponsored", "ad", "promo"]
        }}
        """

        try:
            # response = await self.client.chat.completions.create(
            #     model=settings.OPENAI_MODEL,
            #     messages=[{"role": "system", "content": "You are a professional web scraping expert."}, 
            #               {"role": "user", "content": prompt}],
            #     response_format={"type": "json_object"}
            # )
            # data = json.loads(response.choices[0].message.content)

            response = await self.client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            cleaned_text = response.text.replace('```json', '').replace('```', '').strip()
            parsed_response = json.loads(cleaned_text)
            logger.success(f"🤖 AI generated: {parsed_response}")
            
            # Ensure we have a dict, sometimes AI returns a list of one dict
            if isinstance(parsed_response, list) and len(parsed_response) > 0:
                parsed_response = parsed_response[0]

            if not isinstance(parsed_response, dict):
                 raise ValueError(f"AI returned invalid structure: {type(parsed_response)} (Expected dict)")

            if not parsed_response.get("container_css") or not parsed_response.get("title_css"): return None
            
            domain = urlparse(url).netloc.replace("www.", "")
            
            return ScrapingRule(
                domain=domain,
                site_name=parsed_response.get("site_name", "Unknown Shop"),
                emoji=parsed_response.get("emoji", "🛒"),
                container_css=parsed_response.get("container_css") or "div", # Safe default
                title_css=parsed_response.get("title_css") or "h1",
                brand_css=parsed_response.get("brand_css"), # New field
                concentration_css=parsed_response.get("concentration_css"),
                price_css=parsed_response.get("price_css"),
                image_css=parsed_response.get("image_css"),
                next_page_css=parsed_response.get("next_page_css"),
                negative_keywords=json.dumps(parsed_response.get("negative_keywords", [])),
                # Special logic for deep scraping
                use_detail_page=bool(parsed_response.get("detail_trigger_text") or domain == "notino.lv"),
                detail_trigger_text=parsed_response.get("detail_trigger_text")
            )
        except Exception as e:
            logger.error(f"AI error: {e}")
            return None

    async def generate_detail_rule(self, url: str, html_content: str) -> dict:
        """
        Analyzes a single product page to find how variants (volumes/prices) are structured.
        """
        logger.info(f"🧠 AI Deep Analysis for product page: {url}...")
        # Use strict limit for Detail Page to avoid 429 and timeouts
        clean_content = self.clean_html(html_content, limit=50000)
        
        prompt = f"""
        Act as a Senior Web Scraper.
        Target Product URL: {url}
        
        Task: Analyze the product page HTML and find where different variants (e.g., volumes like 30ml, 50ml, 100ml) and their prices are located.
        
        CRITICAL RULES:
        1. **Variant Container**: Find the CSS selector for the element that wraps EACH variant option (e.g. a list item or a div in a grid).
        2. **Variant Name**: Selector (relative to container) for the text describing the variant (e.g. "50 ml").
        3. **Variant Price**: Selector (relative to container) for the price of this specific variant.
        4. **Stability**: Prefer `data-testid` or semantic classes.
        
        HTML SNIPPET:
        {clean_content}
        
        RETURN JSON ONLY:
        {{
            "variant_container_css": "selector for the repeated variant element",
            "variant_name_css": "selector for volume/name relative to container",
            "variant_price_css": "selector for price relative to container"
        }}
        """

        try:
            # response = await self.client.chat.completions.create(
            #     model=settings.OPENAI_MODEL,
            #     messages=[{"role": "system", "content": "You are a professional web scraping expert."}, 
            #               {"role": "user", "content": prompt}],
            #     response_format={"type": "json_object"}
            # )
            # data = json.loads(response.choices[0].message.content)

            response = await self.client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            cleaned_text = response.text.replace('```json', '').replace('```', '').strip()
            data = json.loads(cleaned_text)
            
            # Ensure we have a dict, sometimes AI returns a list of one dict
            if isinstance(data, list) and len(data) > 0:
                data = data[0]
            
            if not isinstance(data, dict):
                logger.error(f"AI returned invalid structure: {type(data)}")
                return {}

            logger.success(f"📌 AI Detail Rule generated: {data}")
            return data
        except Exception as e:
            logger.error(f"AI Detail Analysis error: {e}")
            return {}

ai_generator = AIGenerator()
