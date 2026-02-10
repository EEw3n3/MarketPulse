import asyncio
import sys
import os
from loguru import logger

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.browser import browser_manager

async def debug_product_page(url: str):
    await browser_manager.start()
    # Try with different wait conditions
    
    logger.info(f"Checking URL: {url}")
    
    # 1. Standard Turbo (domcontentloaded)
    html = await browser_manager.get_page_content(url, fast_mode=True)
    with open("debug_turbo.html", "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"Turbo HTML length: {len(html)}")

    # 2. Full Steiner (with more wait)
    # We'll manually use a context here to test
    context = await browser_manager.get_context()
    page = await context.new_page()
    await page.goto(url, wait_until="networkidle")
    html_idle = await page.content()
    with open("debug_idle.html", "w", encoding="utf-8") as f:
        f.write(html_idle)
    logger.info(f"NetworkIdle HTML length: {len(html_idle)}")
    
    await context.close()
    await browser_manager.stop()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    url = "https://www.notino.lv/armani/emporio-stronger-with-you-intensely-smarzdensedp-vriesiem/p-15802363/"
    asyncio.run(debug_product_page(url))
