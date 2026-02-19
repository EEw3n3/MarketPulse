import asyncio
import sys
import os
from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.domain.models import ScrapingRule

LAB_DB_URL = "sqlite+aiosqlite:///lab/lab_test.db"
lab_engine = create_async_engine(LAB_DB_URL, echo=False)

async def reset_rule():
    async_session = sessionmaker(lab_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        # Find the rule
        stmt = select(ScrapingRule).where(ScrapingRule.domain == "notino.lv")
        result = await session.execute(stmt)
        rule = result.scalar_one_or_none()
        
        if rule:
            print(f"🗑️ Deleting rule for: {rule.domain} (Site: {rule.site_name})")
            print(f"   Old Next Page CSS: {rule.next_page_css}")
            await session.delete(rule)
            await session.commit()
            print("✅ Rule deleted. Next run will regenerate it.")
        else:
            print("Running clean. No rule found for notino.lv.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(reset_rule())
