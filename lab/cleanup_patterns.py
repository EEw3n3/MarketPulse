import asyncio
import sys
import os
from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.domain.models import SharedPattern

LAB_DB_URL = "sqlite+aiosqlite:///lab/lab_test.db"
lab_engine = create_async_engine(LAB_DB_URL, echo=False)

async def clean_patterns():
    async_session = sessionmaker(lab_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        # 1. Find the toxic .nextPage pattern
        stmt = select(SharedPattern).where(
            (SharedPattern.pattern_type == "next_page") & 
            (SharedPattern.css_selector == ".nextPage")
        )
        results = await session.execute(stmt)
        patterns = results.scalars().all()
        
        if patterns:
            print(f"🚮 Found {len(patterns)} bad patterns for .nextPage. Deleting...")
            for p in patterns:
                await session.delete(p)
            await session.commit()
            print("✨ Knowledge base cleaned.")
        else:
            print("✅ No bad patterns found.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(clean_patterns())
