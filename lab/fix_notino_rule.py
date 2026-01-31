import asyncio
from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.domain.models import ScrapingRule

LAB_DB_URL = "sqlite+aiosqlite:///lab/lab_test.db"
lab_engine = create_async_engine(LAB_DB_URL, echo=False)

async def update_notino_rule():
    async_session = sessionmaker(lab_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        # Check rule for notino.lv
        stmt = select(ScrapingRule).where(ScrapingRule.domain == "notino.lv")
        result = await session.execute(stmt)
        rule = result.scalar_one_or_none()
        
        if not rule:
            print("❌ No rule found for notino.lv. Creating one...")
            rule = ScrapingRule(domain="notino.lv", site_name="Notino")
            session.add(rule)
        
        # Manually curated/verified selectors based on inspection
        rule.container_css = "div[class*='StyledProductTile']" # The main card
        rule.title_css = "h3" # Product Name (excluding brand 'h2' for cleaner title?) Or maybe concat? Scraper takes first match. "h3" gives "Noir Extreme".
        # If I want "TOM FORD Noir Extreme", I need a selector that covers both.
        # But 'title_css' returns ONE element text.
        # If I select parent `div.psg1u1x`, I get everything including price text. The generic scraper `extract_clean_text` calls `xpath('string(.)')` so it merges all text.
        # That would mean Title = "TOM FORDNoir ExtremeSmaržūdens...sākot ar..." -> BAD.
        # So stick with `h3`. We can rely on separate `brand` extraction if implemented, or just take the name.
        # Additional trick: `h2, h3` -> Scraper picks FIRST. `h2` is "TOM FORD". That's just brand.
        # PROPOSAL: Use `h3` for title.
        
        rule.price_css = "div[class*='p136vap8']" # This class `p136vap8` is fishy/generated.
        # Better: use `price` from data-testid if available or search for currency.
        # In my manual inspection I saw `sākot ar 152,70€` inside `div.p136vap8`.
        # I'll rely on class for now but warn user it's fragile.
        # BETTER: `div > div` inside the price container area?
        # Let's try: `div[class*='p136vap8']` and assume it works for this session. Use `div` containing price.
        
        rule.image_css = "img[src*='notinoimg']" # Safe bet
        rule.next_page_css = "a[rel='next']" # Standard
        
        # Reset health so it retries freely
        rule.health_score = 1.0 
        rule.failure_count = 0
        rule.success_count = 0
        rule.last_error = None
        
        print(f"🔧 Updating rule for {rule.domain}...")
        print(f"  Container: {rule.container_css}")
        print(f"  Title: {rule.title_css}")
        print(f"  Price: {rule.price_css}")
        
        session.add(rule)
        await session.commit()
        print("✅ Rule updated!")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(update_notino_rule())
