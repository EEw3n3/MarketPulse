import asyncio
import sys
import os
from loguru import logger

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.core.browser import browser_manager

async def check():
    await browser_manager.start()
    url = "https://www.notino.lv/armani/emporio-stronger-with-you-intensely-smarzdensedp-vriesiem/p-15802363/"
    html = await browser_manager.get_page_content(url, fast_mode=True)
    print(f"Length: {len(html)}")
    print("Start of HTML:")
    print(html[:1000])
    await browser_manager.stop()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(check())
