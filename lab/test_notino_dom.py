import asyncio
from playwright.async_api import async_playwright
import json

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Navigating...")
        await page.goto("https://www.notino.lv/rabanne/phantom-in-red-smarzas-vriesiem/", wait_until="domcontentloaded")
        
        script_text = await page.evaluate("() => { let s = document.querySelector('#__NEXT_DATA__'); return s ? s.innerText : ''; }")
        if script_text:
             print("FOUND __NEXT_DATA__")
             
        tiles = await page.locator("div[id^='pd-variant'], [data-testid*='variant']").all()
        for t in tiles:
            text = await t.inner_text()
            print("TILE:", text.replace('\n', ' '))
            
        await browser.close()

asyncio.run(run())
