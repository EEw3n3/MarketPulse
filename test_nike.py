import asyncio
import sys
from loguru import logger
from app.core.client import stealth_client
# Импортируем менеджер браузера (убедись, что файл app/core/browser.py существует)
# Если его нет, тест Tier 3 упадет, но Tier 1 сработает.
try:
    from app.core.browser import browser_manager
    HAS_BROWSER = True
except ImportError:
    HAS_BROWSER = False
    logger.warning("⚠️ BrowserManager не найден. Tier 3 будет пропущен.")

# Цель: Мужская обувь Nike (Категория)
TARGET_URL = "https://www.nike.com/w/mens-shoes-nik1zy7ok"

async def test_tier_1():
    """
    TIER 1: Проверка TLS Spoofing (curl_cffi)
    Пытаемся притвориться Chrome 120 и скачать HTML.
    """
    logger.info("⚔️ [TIER 1] Проверка curl_cffi (TLS Spoofing)...")
    try:
        # Инициализируем сессию
        await stealth_client.init_session()
        
        html = await stealth_client.get_page(TARGET_URL)
        
        if not html:
            logger.error("❌ [TIER 1] Пустой ответ или ошибка сети.")
            return False
            
        if "Access Denied" in html or "403 Forbidden" in html:
            logger.error("❌ [TIER 1] БЛОКИРОВКА! (Access Denied / 403)")
            return False
            
        # Проверяем специфичные для Nike признаки успеха
        if "nike.com" in html:
            logger.success(f"✅ [TIER 1] ПРОБИТИЕ! HTML получен (Длина: {len(html)}).")
            # Проверим, есть ли товары в HTML (или они только в JS)
            if "product-card" in html or "product-grid" in html:
                logger.success("   -> И товары тоже видны в HTML!")
            else:
                logger.warning("   -> Но товаров в чистом HTML нет (нужен JS рендеринг).")
            return True
            
        logger.warning("⚠️ [TIER 1] Статус 200, но контент странный.")
        return False
        
    except Exception as e:
        logger.error(f"❌ [TIER 1] Критическая ошибка: {e}")
        return False

async def test_tier_3():
    """
    TIER 3: Проверка Полноценного Браузера (Playwright)
    """
    if not HAS_BROWSER:
        return False
        
    logger.info("🚜 [TIER 3] Проверка Playwright (Браузер)...")
    try:
        # Загружаем страницу
        html = await browser_manager.get_page_content(TARGET_URL)
        
        if not html:
            logger.error("❌ [TIER 3] Браузер не вернул контент.")
            return False

        if "Access Denied" in html:
            logger.error("❌ [TIER 3] БЛОКИРОВКА БРАУЗЕРА!")
            return False

        # Ищем признаки товаров (классы Nike часто меняются, ищем общие)
        # Обычно Nike использует 'product-card', 'product-grid__items' и т.д.
        if "product-card" in html or "wall-image-loader" in html or "Price-characteristic" in html:
            logger.success(f"✅ [TIER 3] ПОЛНАЯ ПОБЕДА! Товары загружены через JS.")
            return True
        else:
            logger.warning("⚠️ [TIER 3] Доступ есть, но товаров не видно. Возможно, защита Akamai скрыла их.")
            return False
            
    except Exception as e:
        logger.error(f"❌ [TIER 3] Ошибка браузера: {e}")
        return False

async def main():
    logger.info(f"🎯 ЦЕЛЬ: {TARGET_URL}")
    print("-" * 40)
    
    # Запускаем Tier 1
    t1_result = await test_tier_1()
    print("-" * 40)
    
    # Запускаем Tier 3
    t3_result = await test_tier_3()
    print("-" * 40)

    # ИТОГИ
    print("\n📊 ОТЧЕТ РАЗВЕДКИ NIKE:")
    print(f"Tier 1 (TLS Request): {'✅ WIN' if t1_result else '❌ FAIL'}")
    print(f"Tier 3 (Browser):     {'✅ WIN' if t3_result else '❌ FAIL'}")
    
    # Закрываем ресурсы
    await stealth_client.close()
    if HAS_BROWSER:
        await browser_manager.stop()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())