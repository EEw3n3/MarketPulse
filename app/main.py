import asyncio
import sys
from loguru import logger

from app.core.database import init_db, async_session
from app.core.client import stealth_client
from app.core.browser import browser_manager
from app.services.ai_generator import ai_generator
from app.services.scraper import scraper_service

TARGETS = [
    {
        "url": "https://www.rdveikals.lv/categories/lv/388/sort/5/filter/0_0_74_0/page/1/Mobilie-telefoni.html",
        "search_term": "Mobile Phones",
        "category": "Electronics"
    }
]

TARGET_COUNT = 100

async def get_hybrid_html(url: str, force_browser: bool = False) -> str | None:
    """
    Attempts to fetch HTML content using a tiered approach:
    Tier 1: Fast stealth client
    Tier 3: Full browser rendering (if Tier 1 fails or if forced).
    """
    if force_browser:
        logger.warning(f"🚜 [Tier 3] Принудительный запуск браузера для {url}...")
        try:
            html = await browser_manager.get_page_content(url)
            if html and len(html) > 1000:
                logger.success(f"✅ [Tier 3] Браузер отрендерил страницу! ({len(html)} байт)")
                return html
        except Exception as e:
            logger.critical(f"❌ [Tier 3] Ошибка браузера: {e}")
        return None

    logger.info(f"⚡ [Tier 1] Пробую быстрый метод для {url}...")
    try:
        html = await stealth_client.get_page(url)
        if html and len(html) > 1000 and "Access Denied" not in html:
            logger.success(f"✅ [Tier 1] Успех! Получено {len(html)} байт.")
            return html
        else:
            logger.warning("⚠️ [Tier 1] Неудачно (блокада или пустой ответ).")
    except Exception as e:
        logger.error(f"⚠️ [Tier 1] Ошибка: {e}")

    return await get_hybrid_html(url, force_browser=True)

async def process_target(session, target: dict):
    url = target["url"]
    search_term = target["search_term"]
    category = target.get("category", "General")

    logger.info(f"\n🏁 НАЧИНАЕМ ПРОВЕРКУ: {url}")
    logger.info(f"🎯 Поиск: {search_term} | Категория: {category}")
    
    # 0. Находим или создаем Группу
    from app.domain.models import ProductGroup
    stmt = select(ProductGroup).where(ProductGroup.name == search_term)
    group = (await session.execute(stmt)).scalar_one_or_none()
    
    if not group:
        group = ProductGroup(name=search_term, category=category)
        session.add(group)
        await session.flush()
        logger.info(f"📁 Создана новая группа: {search_term}")

    html = await get_hybrid_html(url)
    if not html: return

    rule = await ai_generator.get_or_create_rule(session, url, html)
    if not rule:
        logger.warning("🤔 Правило не создано. Пробую Browser...")
        html = await get_hybrid_html(url, force_browser=True)
        rule = await ai_generator.get_or_create_rule(session, url, html)
        
    if not rule:
        logger.error("❌ Не удалось создать правило.")
        return

    logger.info(f"📦 [{rule.site_name}] Попытка сбора #1...")
    products = await scraper_service.scrape_catalog(
        session, url, html, max_items=TARGET_COUNT, group_id=group.id
    )
    
    report = scraper_service.validate_dataset(products)
    
    if not products or not report["is_healthy"]:
        logger.warning(f"🚨 [ALARM] Данные неудовлетворительны: {report.get('error', 'Unknown')}")
        logger.warning(f"♻️ ЗАПУСК ПРОТОКОЛА ВОССТАНОВЛЕНИЯ (Tier 3 + Force Refresh)...")
        
        html_rendered = await get_hybrid_html(url, force_browser=True)
        if html_rendered:
            new_rule = await ai_generator.get_or_create_rule(
                session, 
                url, 
                html_rendered, 
                force_refresh=True,
                error_hint=report.get("error")
            )
            
            if new_rule:
                rule = new_rule 
                logger.info(f"📦 [{rule.site_name}] Попытка сбора #2 (FIXED)...")
                products = await scraper_service.scrape_catalog(
                    session, url, html_rendered, max_items=TARGET_COUNT, group_id=group.id
                )

    # Итоговый отчет
    if products and rule:
        final_bad_prices = sum(1 for p in products if p.price == 0)
        logger.success(f"🎉 [{rule.site_name}] Сбор завершен!")
        print(f"\n{rule.emoji}  --- РЕЗУЛЬТАТЫ ---")
        print(f"   Группа: {group.name}")
        print(f"   Собрано: {len(products)}")
        for p in products[-1:]:
            print(f"   Пример: {p.title[:50]} | {p.price} | {p.image_url[:40] if p.image_url else 'No Img'}...")
        print(f"{'—' * 75}\n")
    else:
        logger.error(f"❌ ФИНАЛЬНЫЙ ПРОВАЛ.")

# Семафор для ограничения количества одновременных задач парсинга
MAX_CONCURRENT_SCRAPES = 3
scrape_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SCRAPES)

async def process_target_worker(target: dict):
    """
    Обертка для process_target, которая соблюдает ограничения семафора 
    и управляет жизненным циклом сессии.
    """
    async with scrape_semaphore:
        async with async_session() as session:
            try:
                await process_target(session, target)
            except Exception as e:
                logger.error(f"💥 Критическая ошибка при обработке {target['url']}: {e}")

async def main():
    logger.info("🚀 Запуск MarketPulse: Intelligence Backend")
    await init_db()
    
    # Инициализация сессии клиента
    await stealth_client.init_session()

    try:
        # Запускаем задачи параллельно
        tasks = [process_target_worker(target) for target in TARGETS]
        await asyncio.gather(*tasks)
    finally:
        await stealth_client.close()
        await browser_manager.stop()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
