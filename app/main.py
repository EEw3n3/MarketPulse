import asyncio
import sys
from loguru import logger

from app.core.database import init_db, async_session
from app.core.client import stealth_client
from app.core.browser import browser_manager
from app.services.ai_generator import ai_generator
from app.services.scraper import scraper_service

TARGETS = [
    "https://www.rdveikals.lv/categories/lv/388/sort/5/filter/0_0_74_0/page/1/Mobilie-telefoni.html"
]

TARGET_COUNT = 100

async def get_hybrid_html(url: str, force_browser: bool = False) -> str | None:
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

async def process_target(session, url: str):
    logger.info(f"\n🏁 НАЧИНАЕМ СТРЕСС-ТЕСТ: {url}")
    logger.info(f"🎯 Цель: Собрать {TARGET_COUNT} товаров с правильными ценами.")
    
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
    products = await scraper_service.scrape_catalog(session, url, html, max_items=TARGET_COUNT)
    
    # --- ИСПОЛЬЗУЕМ ЦЕНТРАЛИЗОВАННУЮ ПРОВЕРКУ ---
    report = scraper_service.validate_dataset(products)
    
    if not products or not report["is_healthy"]:
        logger.warning(f"🚨 [ALARM] Данные неудовлетворительны: {report.get('error', 'Unknown')}")


    if not products or not report["is_healthy"]:
        logger.warning(f"🚨 [ALARM] Данные неудовлетворительны. Запускаем восстановление.")
        logger.warning(f"♻️ ЗАПУСК ПРОТОКОЛА ВОССТАНОВЛЕНИЯ (Tier 3 + Force Refresh)...")
        
        html_rendered = await get_hybrid_html(url, force_browser=True)
        if html_rendered:
            logger.info("🧠 Регенерация правил с учетом ошибок...")
            # Передаем подсказку об ошибке, чтобы ИИ не наступил на те же грабли
            new_rule = await ai_generator.get_or_create_rule(
                session, 
                url, 
                html_rendered, 
                force_refresh=True,
                error_hint=report.get("error")
            )

            
            if new_rule:
                rule = new_rule # Обновляем переменную rule
                logger.info(f"📦 [{rule.site_name}] Попытка сбора #2 (FIXED)...")
                products = await scraper_service.scrape_catalog(session, url, html_rendered, max_items=TARGET_COUNT)
            else:
                logger.error("❌ ИИ не смог создать новое правило даже после рестарта.")
                return

    # Итоговый отчет
    if products and rule:
        final_bad_prices = sum(1 for p in products if p.price == 0)
        
        logger.success(f"🎉 [{rule.site_name}] Сбор завершен!")
        print(f"\n{rule.emoji}  --- РЕЗУЛЬТАТЫ ---")
        print(f"   Собрано: {len(products)}")
        print(f"   Без цены: {final_bad_prices}")
        
        if len(products) >= TARGET_COUNT and final_bad_prices == 0:
             logger.success("✅ ТЕСТ ПРОЙДЕН ИДЕАЛЬНО!")
        elif len(products) >= TARGET_COUNT:
             logger.warning("⚠️ КОЛИЧЕСТВО ОК, НО ЕСТЬ ОШИБКИ В ЦЕНАХ.")
        else:
             logger.warning(f"⚠️ НЕ ХВАТИЛО ТОВАРОВ: {len(products)}/{TARGET_COUNT}")
             
        print("\n   Последние 3 товара:")
        for p in products[-3:]:
            print(f"   ▪️ {p.title[:50]:<50} | 💰 {str(p.price):>8}")
        print(f"{'—' * 75}\n")
    else:
        logger.error(f"❌ ФИНАЛЬНЫЙ ПРОВАЛ.")

async def main():
    logger.info("🚀 Запуск MarketPulse: Quality Control Mode")
    await init_db()
    await stealth_client.init_session()

    async with async_session() as session:
        for url in TARGETS:
            await process_target(session, url)

    await stealth_client.close()
    await browser_manager.stop()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())