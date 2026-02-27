import asyncio
import json
from loguru import logger
from playwright.async_api import async_playwright
import sys
import os

async def test_interception():
    url = "https://www.notino.lv/narciso-rodriguez/for-him-bleu-noir-smarzdensedp-vriesiem/"
    logger.info(f"Targeting: {url}")
    
    requests_data = []
    responses_data = []
    
    async def handle_request(request):
        try:
            req_url = request.url
            junk = ['google', 'facebook', 'hotjar', 'metrics', 'clarity', 'trustpilot', 'doubleclick', 'ads']
            if any(j in req_url.lower() for j in junk):
                return
            
            if request.method in ["POST", "PUT", "PATCH"]:
                post_data = request.post_data_json
                if post_data:
                    requests_data.append({"url": req_url, "data": post_data})
        except Exception:
            pass

    async def handle_response(response):
        try:
            if "application/json" in response.headers.get("content-type", "").lower():
                res_url = response.url
                junk = ['google', 'facebook', 'hotjar', 'metrics', 'clarity', 'trustpilot', 'doubleclick', 'ads']
                if any(j in res_url.lower() for j in junk):
                    return
                json_data = await response.json()
                responses_data.append({"url": res_url, "data": json_data})
        except Exception as e:
            pass            

    async with async_playwright() as p:
        # Running non-headless so you can see it physically on screen
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        page.on("request", handle_request)
        page.on("response", handle_response)
        
        logger.info("Loading page...")
        await page.goto(url, wait_until="domcontentloaded")
        
        logger.info("Waiting 4 seconds for initial trackers...")
        await asyncio.sleep(4)
        
        logger.info("Attempting to find and click the variant '50 ml' or similar...")
        # Try to click on a volume variant div/button
        # Notino variants often contain the text "50 ml"
        try:
            variant_els = await page.locator("text='50 ml'").all()
            if len(variant_els) > 0:
                for el in variant_els:
                    if await el.is_visible():
                        await el.click()
                        logger.info("Clicked '50 ml' variant.")
                        break
            else:
                logger.warning("Could not find '50 ml' visible text. Trying a generic click on variants.")
                await page.locator(".pd-variant-label, [data-testid*='variant']").first.click()
        except Exception as e:
            logger.warning(f"Failed to click variant (or maybe we already clicked it if we used generic?): {e}")
            
        logger.info("Waiting 5 seconds for detail tracking requests to fire...")
        await asyncio.sleep(5)
        
        logger.info(f"Captured {len(requests_data)} POST/PUT Data Payloads")
        
        logger.info("=== INTERCEPTED REQUEST PAYLOADS (LuigisBox/Events) ===")
        found_target = False
        for req in requests_data:
            req_url = req["url"]
            if "detail" in req_url or "events" in req_url or "collector" in req_url:
                found_target = True
                logger.success(f"🎯 FOUND TRACKING TARGET (REQUEST): {req_url}")
                try:
                    print(json.dumps(req["data"], indent=2, ensure_ascii=False))
                except Exception:
                    print(f"Raw data: {req['data']}")

        if not found_target:
            logger.warning("No tracking request events found (collector/events/detail).")
            
        logger.info("=== INTERCEPTED JSON RESPONSES ===")
        found_response = False
        for res in responses_data:
            res_url = res["url"]
            # Look for pricing or variant data in standard API responses
            if "api" in res_url and "price" in str(res.get("data", "")).lower():
                found_response = True
                logger.success(f"💸 Found 'price' in RESPONSE: {res_url}")
                # Print snippet of data
                try:
                    snippet = json.dumps(res["data"])[:500]
                    print(snippet + "...")
                except Exception:
                    print(f"Raw data snippet: {res['data']}")

        if not found_response:
             logger.warning("No standard API JSON responses containing 'price' found.")
             
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_interception())
