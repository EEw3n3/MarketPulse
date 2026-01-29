import asyncio
from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.domain.models import ScrapingRule

# Use LAB DB URL
LAB_DB_URL = "sqlite+aiosqlite:///lab/lab_test.db"
lab_engine = create_async_engine(LAB_DB_URL, echo=False)

async def inspect_rules():
    async_session = sessionmaker(lab_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        stmt = select(ScrapingRule).where(ScrapingRule.domain == "makeup.lv")
        result = await session.execute(stmt)
        rule = result.scalar_one_or_none()
        if rule:
            print("\n--- [RULE FOR MAKEUP.LV] ---")
            print(f"Container: {rule.container_css}")
            print(f"Title:     {rule.title_css}")
            print(f"Price:     {rule.price_css}")
            print(f"Next Page: {rule.next_page_css}")
            print("-" * 30)
        else:
            print("ℹ️ No rule found for makeup.lv in LAB database.")

async def delete_rule():
    async_session = sessionmaker(lab_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        stmt = select(ScrapingRule).where(ScrapingRule.domain == "makeup.lv")
        result = await session.execute(stmt)
        rule = result.scalar_one_or_none()
        if rule:
            await session.delete(rule)
            await session.commit()
            print("✅ Rule for makeup.lv DELETED.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "delete":
        asyncio.run(delete_rule())
    else:
        asyncio.run(inspect_rules())
