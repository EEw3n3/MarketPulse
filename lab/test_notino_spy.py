import asyncio
import json
from decimal import Decimal
from playwright.async_api import async_playwright

async def run():
    url = "https://www.notino.lv/versace/man-eau-fraiche-tualetesdensedt-vriesiem/"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        intercepted = {"luigisbox": [], "detail": []}
        
        async def handle_request(request):
            try:
                if request.method in ["POST", "PUT"]:
                    req_url = request.url
                    if "collector-lv.notino.luigisbox.com/events" in req_url:
                        data = request.post_data_json
                        if data: intercepted["luigisbox"].append(data)
                    elif "/api/tracking/web/view/detail" in req_url:
                        data = request.post_data_json
                        if data: intercepted["detail"].append(data)
            except:
                pass
                
        page.on("request", handle_request)
        
        print("1. Loading page...")
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(2)
        
        print("1.5. Handling cookies...")
        cookie_selectors = [
            "button:has-text('Pieņemt visu')", "button:has-text('Piekrītu')", 
            "button:has-text('Apstiprināt')", "button:has-text('Piekrist visiem')", 
            "button:has-text('Pieņemt')", "#onetrust-accept-btn-handler", ".cookie-consent-accept"
        ]
        for btn_sel in cookie_selectors:
            cookie_btn = page.locator(btn_sel).first
            if await cookie_btn.is_visible(timeout=1000):
                print(f" -> Found cookie banner via {btn_sel}, clicking it!")
                await cookie_btn.click(force=True)
                await asyncio.sleep(1.0)
                break
        
        print("2. Clicking variants...")
        variant_els = await page.locator("div[data-testid*='variant'], span[class*='variant'], .pd-variant-label").all()
        if not variant_els:
            variant_els = await page.locator("div:has-text(' ml'), button:has-text(' ml')").all()
            
        for i, el in enumerate(variant_els):
            if await el.is_visible():
                print(f" -> Clicking: {await el.inner_text()}")
                if i == 0:
                    for btn_sel in cookie_selectors:
                        btn = page.locator(btn_sel).first
                        if await btn.is_visible(timeout=100):
                            print(f" ->  Banner reappeared! Force clicking again.")
                            await btn.click(force=True)
                            await asyncio.sleep(0.5)
                await el.click(timeout=1500, force=True)
                await asyncio.sleep(0.5)
                
        await asyncio.sleep(1) # wait for net
        
        print("\n=== PHASE 2: DETAIL PAYLOADS (Vol/Available) ===")
        variants_map = {}
        for req_data in intercepted["detail"]:
            code = req_data.get("code")
            size = req_data.get("size")
            sizeUnit = req_data.get("sizeUnit")
            if code and size:
                variants_map[code] = f"{size} {sizeUnit}"
                print(f" [Detail] Found Code: {code} -> {size} {sizeUnit}")
                
        print("\n=== PHASE 3: LUIGISBOX PAYLOADS (Prices) ===")
        for req_data in intercepted["luigisbox"]:
            events = req_data.get("events", [])
            for event in events:
                event_data = event.get("data", {})
                products = list(event_data.get("products", []))
                if "related_to" in event_data:
                    products.extend(event_data["related_to"].get("products", []))
                    
                for p in products:
                    p_code = p.get("product_code")
                    p_disc = p.get("discount_price")
                    p_full = p.get("full_price")
                    if p_code and (p_disc or p_full):
                        print(f" [LuigisBox] Found Product_Code: {p_code} | Discount: {p_disc} | Full: {p_full}")
        
        print("\n=== PHASE 4: MATCHING RESULTS ===")
        for code, vol in variants_map.items():
            print(f" Result -> Code: {code} | Volume: {vol} | Did we find price?: ... (Check above)")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
