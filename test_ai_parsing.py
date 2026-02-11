
import asyncio
from app.core.browser import browser_manager
from app.services.ai_generator import ai_generator
from loguru import logger

# URL для теста сложного товара с вариантами (разные объемы)
TEST_URL = "https://www.notino.lv/hugo-boss/boss-bottled-tualetesdensedt-vriesiem/p-63109/"

async def run_ai_test():
    logger.info(f"🧪 STARING AI PARSING TEST for: {TEST_URL}")
    
    # 1. Запускаем браузер и получаем HTML
    logger.info("🚜 Launching browser to get HTML...")
    await browser_manager.start()
    html_content = await browser_manager.get_page_content(TEST_URL)
    
    if not html_content:
        logger.error("❌ Failed to get HTML content")
        return

    logger.info(f"📄 HTML received ({len(html_content)} chars). Sending to AI...")

    # 2. Просим ИИ найти селекторы вариантов
    ai_rule = await ai_generator.generate_detail_rule(TEST_URL, html_content)
    
    logger.success("✅ AI RESULT:")
    print(ai_rule)
    
    # 3. Закрываем браузер
    await browser_manager.close()

if __name__ == "__main__":
    asyncio.run(run_ai_test())
