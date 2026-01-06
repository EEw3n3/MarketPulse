import asyncio
import sys
from sqlmodel import select
from app.core.database import async_session
from app.domain.models import ScrapingRule

async def inspect_rules():
    async with async_session() as session:
        statement = select(ScrapingRule)
        results = await session.execute(statement)
        rules = results.scalars().all()
        
        if not rules:
            print("\n❌ В базе пока нет сохраненных правил. Запустите парсер (main.py).")
            return

        print(f"\n🧠 СОХРАНЕННЫЕ ПРАВИЛА ИИ: {len(rules)}")
        print("-" * 120)
        
        for r in rules:
            print(f"Магазин: {r.emoji} {r.site_name} ({r.domain})")
            print(f"  ├─ Карточка:   {r.container_css}")
            print(f"  ├─ Заголовок:  {r.title_css}")
            print(f"  ├─ Цена:       {r.price_css}")
            print(f"  └─ Пагинация:  {r.next_page_css}")
            print("-" * 120)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(inspect_rules())
