import asyncio
import sys
from loguru import logger
from sqlmodel import select

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
    },
    # Можно добавить другие сайты позже для сравнения в одной группе
]

TARGET_COUNT = 20 # Уменьшим для быстрого теста бэкенда

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

    logger.info(f"📦 [{rule.site_name}] Попытка сбора...")
    products = await scraper_service.scrape_catalog(
        session, url, html, max_items=TARGET_COUNT, group_id=group.id
    )
    
    report = scraper_service.validate_dataset(products)
    
    if not products or not report["is_healthy"]:
        logger.warning(f"🚨 [ALARM] Данные неудовлетворительны. Запуск восстановления...")
        html_rendered = await get_hybrid_html(url, force_browser=True)
        if html_rendered:
            new_rule = await ai_generator.get_or_create_rule(
                session, url, html_rendered, force_refresh=True, error_hint=report.get("error")
            )
            if new_rule:
                await scraper_service.scrape_catalog(
                    session, url, html_rendered, max_items=TARGET_COUNT, group_id=group.id
                )

# Семафор для ограничения одновременных задач
MAX_CONCURRENT_SCRAPES = 3
scrape_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SCRAPES)

async def process_target_worker(target: dict):
    async with scrape_semaphore:
        async with async_session() as session:
            try: await process_target(session, target)
            except Exception as e: logger.error(f"💥 Ошибка {target['url']}: {e}")

async def main():
    logger.info("🚀 Запуск MarketPulse: Intelligence CLI")
    await init_db()
    await stealth_client.init_session()

    try:
        # 1. Запускаем параллельный парсинг
        tasks = [process_target_worker(target) for target in TARGETS]
        await asyncio.gather(*tasks)

        # 2. ФИНАЛЬНЫЙ АНАЛИЗ (Вместо API)
        logger.info("\n📊 ГЕНЕРАЦИЯ ОТЧЕТА ПО ГРУППАМ...")
        from app.services.analyzer import price_analyzer
        from app.domain.models import ProductGroup

        async with async_session() as session:
            groups_stmt = select(ProductGroup)
            groups = (await session.execute(groups_stmt)).scalars().all()

            for g in groups:
                analysis = await price_analyzer.analyze_group(session, g.id)
                if analysis:
                    print(f"\n💎 ОТЧЕТ ПО ГРУППЕ: {g.name}")
                    print(f"   Категория:  {g.category}")
                    print(f"   Ср. цена:   {analysis['avg_group_price']} €")
                    print(f"   Лучшая:     {analysis['best_price']} € ({analysis['best_store']})")
                    print(f"   Экономия:   {analysis['savings']} €")
                    print(f"{'—' * 60}")
                else:
                    print(f"\nℹ️ Группа {g.name} пока пуста.")

    finally:
        await stealth_client.close()
        await browser_manager.stop()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
