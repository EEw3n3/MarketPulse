import asyncio
from app.core.database import async_session
from app.domain.models import ScrapingRule
from sqlmodel import select

async def update_makeup_rule():
    async with async_session() as session:
        stmt = select(ScrapingRule).where(ScrapingRule.domain == "makeup.lv")
        rule = (await session.execute(stmt)).scalar_one_or_none()
        
        if rule:
            rule.container_css = ".simple-slider-list__item:not(.banner)"
            rule.title_css = ".simple-slider-list__name"
            rule.price_css = ".price_item"
            rule.image_css = ".simple-slider-list__image img"
            rule.next_page_css = "li.next a, a[rel='next']"
            session.add(rule)
            await session.commit()
            print("Successfully updated Makeup.lv rule.")
        else:
            print("Makeup.lv rule not found in DB.")

if __name__ == "__main__":
    asyncio.run(update_makeup_rule())
