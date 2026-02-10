import asyncio
import sys
import os
from loguru import logger

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.core.browser import browser_manager

async def check_no_id():
    await browser_manager.start()
    # URL without p-id
    url = "https://www.notino.lv/armani/emporio-stronger-with-you-intensely-smarzdensedp-vriesiem/"
    html = await browser_manager.get_page_content(url, fast_mode=True)
    print(f"Length: {len(html)}")
    print("Title:", html.split("<title>")[1].split("</title>")[0] if "<title>" in html else "No Title")
    with open("debug_no_id.html", "w", encoding="utf-8") as f:
        f.write(html)
    await browser_manager.stop()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(check_no_id())
