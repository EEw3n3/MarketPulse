"""One-time script: delete stale 220.lv and 1a.lv rules so the VERIFIED fast-path triggers fresh."""
import asyncio
from sqlmodel import delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import engine
from app.domain.models import ScrapingRule


async def clear_rules():
    async with AsyncSession(engine) as s:
        result = await s.execute(
            delete(ScrapingRule).where(
                ScrapingRule.domain.in_(["1a.lv", "220.lv"])
            )
        )
        await s.commit()
        print(f"Deleted {result.rowcount} stale rule(s). Ready for fresh VERIFIED fast-path.")


if __name__ == "__main__":
    asyncio.run(clear_rules())
