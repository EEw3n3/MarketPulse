import asyncio
import sys
from urllib.parse import quote_plus
from loguru import logger
from sqlmodel import select

from app.core.database import init_db, async_session
from app.core.client import stealth_client
from app.core.browser import browser_manager
from app.services.ai_generator import ai_generator
from app.services.scraper import scraper_service
from app.services.intent import intent_service

# Больше не используем жестко зашитые TARGETS
# TARGETS = [...] 

TARGET_COUNT = 20 

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
    
    print("\n" + "="*50)
    print("🤖 ДОБРО ПОЖАЛОВАТЬ В MARKETPULSE CLI")
    print("="*50)
    print("Выберите режим работы:")
    print("1. 🎯 Умный Поиск (Interactive Search)")
    print("2. 🚜 Массовый Скрапинг (Category Training / Mass Scrape)")
    print("-" * 50)
    
    choice = input("👉 Выберите вариант (1 или 2): ").strip()
    
    await init_db()
    await stealth_client.init_session()

    try:
        if choice == "1":
            # --- РЕЖИМ 1: УМНЫЙ ПОИСК ---
            user_query = input("\n🎯 Что ищем? (например: iPhone 16): ").strip()
            if not user_query: return
            
            intent = await intent_service.parse_user_query(user_query)
            search_term = intent["search_term"]
            category = intent["category"]
            
            encoded_query = quote_plus(search_term)
            dynamic_targets = [
                {
                    "url": f"https://www.rdveikals.lv/search/lv/word/{encoded_query}/page/1/",
                    "search_term": search_term,
                    "category": category
                },
                {
                     "url": f"https://www.nike.com/w?q={encoded_query}",
                     "search_term": search_term,
                     "category": category
                }
            ]
            
            from app.core.registry import register_domain
            for t in dynamic_targets: register_domain(t["url"])

            tasks = [process_target_worker(target) for target in dynamic_targets]
            await asyncio.gather(*tasks)

        elif choice == "2":
            # --- РЕЖИМ 2: МАССОВЫЙ СКРАПИНГ ---
            print("\n🚜 РЕЖИМ ОБУЧЕНИЯ (Mass Scrape)")
            target_url = input("🔗 Введите URL каталога/категории: ").strip()
            search_term = input("🏷️ Назовите эту группу (например: Nike Shoes): ").strip()
            category = input("📁 Категория (Electronics/Shoes/etc): ").strip() or "General"
            limit = input("🔢 Лимит товаров (по умолчанию 50): ").strip()
            limit = int(limit) if limit.isdigit() else 50
            
            global TARGET_COUNT
            TARGET_COUNT = limit

            from app.core.registry import register_domain
            register_domain(target_url)

            target = {
                "url": target_url,
                "search_term": search_term,
                "category": category
            }
            
            await process_target_worker(target)
        
        else:
            logger.error("Неверный выбор режима.")
            return

        # 5. ФИНАЛЬНЫЙ АНАЛИЗ (только для режима поиска, либо если есть данные)
        logger.info("\n📊 ГЕНЕРАЦИЯ ОТЧЕТА ПО ГРУППАМ...")
        from app.services.analyzer import price_analyzer
        from app.domain.models import ProductGroup

        async with async_session() as session:
            # Если был поиск - берем конкр. группу, если обучение - все новые
            groups_stmt = select(ProductGroup).order_by(ProductGroup.created_at.desc()).limit(1)
            results = await session.execute(groups_stmt)
            groups = results.scalars().all()

            for g in groups:
                analysis = await price_analyzer.analyze_group(session, g.id)
                if analysis:
                    print(f"\n💎 ОТЧЕТ: {g.name}")
                    print(f"   Категория:  {g.category}")
                    print(f"   Кол-во:     {len(g.products)} товаров")
                    print(f"   Ср. цена:   {analysis['avg_group_price']} €")
                    print(f"   Лучшая:     {analysis['best_price']} € ({analysis['best_store']})")
                    print(f"{'—' * 60}")

    finally:
        await stealth_client.close()
        await browser_manager.stop()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
