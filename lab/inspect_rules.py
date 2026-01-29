import asyncio
import os
import sys
from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.domain.models import ScrapingRule

LAB_DB_URL = "sqlite+aiosqlite:///lab/lab_test.db"
engine = create_async_engine(LAB_DB_URL)

async def inspect_rules():
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        stmt = select(ScrapingRule)
        rules = (await session.execute(stmt)).scalars().all()
        for r in rules:
            print(f"\n--- Rule for {r.domain} ---")
            print(f"Container: {r.container_css}")
            print(f"Title:     {r.title_css}")
            print(f"Price:     {r.price_css}")
            print(f"Next Page: {r.next_page_css}")
            print(f"Negative:  {r.negative_keywords}")

if __name__ == "__main__":
    asyncio.run(inspect_rules())
