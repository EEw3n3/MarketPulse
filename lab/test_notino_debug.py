import asyncio
import json
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        url = "https://www.notino.lv/rabanne/phantom-in-red-smarzas-vriesiem/"
        
        intercepted = []
        page.on("request", lambda req: intercepted.append(req.post_data_json) if "luigisbox" in req.url and req.method in ["POST", "PUT"] and req.post_data_json else None)
        
        await page.goto(url, wait_until="networkidle")
        print("Page loaded. Waiting for trackers...")
        
        # Click cookies
        try:
            btn = page.locator("button:has-text('Piekrītu')").first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                print("Clicked cookies!")
                await asyncio.sleep(1)
        except Exception:
            pass
            
        await asyncio.sleep(2)
        
        print("Clicking variants...")
        els = await page.locator("a:has-text('ml'), button:has-text('ml'), div:has-text('ml')").all()
        for el in els:
            if await el.is_visible():
                try:
                    text = await el.inner_text()
                    if "ml" in text:
                        print(f"Clicking {text.replace(chr(10), ' ')}")
                        await el.click(timeout=1000)
                        await asyncio.sleep(1)
                except Exception as e:
                    pass
                    
        print(f"Intercepted {len(intercepted)} payloads")
        for i, data in enumerate(intercepted):
            print(f"--- Payload {i} ---")
            print(json.dumps(data, indent=2))
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
