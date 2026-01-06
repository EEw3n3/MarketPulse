import asyncio
from sqlmodel import select
from sqlalchemy.orm import selectinload
from app.core.database import async_session
from app.domain.models import Product

async def check():
    async with async_session() as session:
        # Загружаем товары вместе с их историей (selectinload)
        statement = select(Product).options(selectinload(Product.history))
        result = await session.execute(statement)
        products = result.scalars().all()
        
        print(f"\n--- ОТЧЕТ ИЗ БАЗЫ ДАННЫХ ---")
        print(f"Всего товаров в базе: {len(products)}")
        
        for p in products[:3]: # Показываем первые 3 товара
            print(f"\n📦 Товар: {p.title}")
            print(f"🔗 Ссылка: {p.url}")
            print(f"📊 Записей в истории цен: {len(p.history)}")
            for h in p.history:
                print(f"   🕒 {h.parsed_at.strftime('%H:%M:%S')} -> {h.price} руб.")

if __name__ == "__main__":
    asyncio.run(check())