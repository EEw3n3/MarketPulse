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

async def delete_notino_rule():
    async_session = sessionmaker(lab_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        stmt = select(ScrapingRule).where(ScrapingRule.domain == "notino.lv")
        result = await session.execute(stmt)
        rule = result.scalar_one_or_none()
        
        if rule:
            await session.delete(rule)
            await session.commit()
            print("✅ Rule for notino.lv DELETED. Next run will trigger AI generation.")
        else:
            print("ℹ️ No rule found for notino.lv.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(delete_notino_rule())
