import asyncio
import sys
from loguru import logger
from app.core.client import stealth_client
# Importing browser manager (ensure app/core/browser.py exists)
# If missing, Tier 3 will fail, but Tier 1 will work.
try:
    from app.core.browser import browser_manager
    HAS_BROWSER = True
except ImportError:
    HAS_BROWSER = False
    logger.warning("⚠️ BrowserManager not found. Tier 3 skipped.")

# Target: Men's Nike Shoes (Category)
TARGET_URL = "https://www.nike.com/w/mens-shoes-nik1zy7ok"

async def test_tier_1():
    """
    TIER 1: TLS Spoofing Check (curl_cffi)
    Trying to pretend to be Chrome 120 and download HTML.
    """
    logger.info("⚔️ [TIER 1] Checking curl_cffi (TLS Spoofing)...")
    try:
        # Initializing session
        await stealth_client.init_session()
        
        html = await stealth_client.get_page(TARGET_URL)
        
        if not html:
            logger.error("❌ [TIER 1] Empty response or network error.")
            return False
            
        if "Access Denied" in html or "403 Forbidden" in html:
            logger.error("❌ [TIER 1] BLOCK! (Access Denied / 403)")
            return False
            
        # Checking specific Nike success signs
        if "nike.com" in html:
            logger.success(f"✅ [TIER 1] BREAKTHROUGH! HTML received (Length: {len(html)}).")
            # Check if items are in HTML (or only in JS)
            if "product-card" in html or "product-grid" in html:
                logger.success("   -> And items are also visible in HTML!")
            else:
                logger.warning("   -> But no items in pure HTML (JS rendering needed).")
            return True
            
        logger.warning("⚠️ [TIER 1] Status 200, but content is strange.")
        return False
        
    except Exception as e:
        logger.error(f"❌ [TIER 1] Critical error: {e}")
        return False

async def test_tier_3():
    """
    TIER 3: Full Browser Check (Playwright)
    """
    if not HAS_BROWSER:
        return False
        
    logger.info("🚜 [TIER 3] Checking Playwright (Browser)...")
    try:
        # Loading page
        html = await browser_manager.get_page_content(TARGET_URL)
        
        if not html:
            logger.error("❌ [TIER 3] Browser returned no content.")
            return False

        if "Access Denied" in html:
            logger.error("❌ [TIER 3] BROWSER BLOCK!")
            return False

        # Looking for item signs (Nike classes change often, look for common ones)
        # Usually Nike uses 'product-card', 'product-grid__items' etc.
        if "product-card" in html or "wall-image-loader" in html or "Price-characteristic" in html:
            logger.success(f"✅ [TIER 3] FULL VICTORY! Items loaded via JS.")
            return True
        else:
            logger.warning("⚠️ [TIER 3] Access granted, but items invisible. Maybe Akamai hidden them.")
            return False
            
    except Exception as e:
        logger.error(f"❌ [TIER 3] Browser error: {e}")
        return False

async def main():
    logger.info(f"🎯 TARGET: {TARGET_URL}")
    print("-" * 40)
    
    # Running Tier 1
    t1_result = await test_tier_1()
    print("-" * 40)
    
    # Running Tier 3
    t3_result = await test_tier_3()
    print("-" * 40)

    # REPORT
    print("\n📊 NIKE RECON REPORT:")
    print(f"Tier 1 (TLS Request): {'✅ WIN' if t1_result else '❌ FAIL'}")
    print(f"Tier 3 (Browser):     {'✅ WIN' if t3_result else '❌ FAIL'}")
    
    # Closing resources
    await stealth_client.close()
    if HAS_BROWSER:
        await browser_manager.stop()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())