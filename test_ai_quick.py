
import asyncio
import os
from google import genai
from google.genai import types
from app.core.browser import browser_manager
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

# Switch to 1.5-flash to bypass quota limits
MODEL = "gemini-3-flash-preview"
TEST_URL = "https://www.notino.lv/hugo-boss/boss-bottled-tualetesdensedt-vriesiem/p-63109/"

async def run_quick_test():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.error("❌ No API Key")
        return

    client = genai.Client(api_key=api_key)

    logger.info(f"🚀 Starting QUICK AI Test using {MODEL}")
    
    # 1. Get HTML
    logger.info("🚜 Getting HTML...")
    await browser_manager.start()
    html_data = await browser_manager.get_page_content(TEST_URL)
    html_content = html_data["html"] if html_data else None
    await browser_manager.stop()
    
    if not html_content:
        logger.error("❌ No HTML")
        return

    # 2. Smart Cleanup using the actual service logic
    from app.services.ai_generator import ai_generator
    
    logger.info("🧹 Cleaning HTML...")
    # Manually call clean logic to see how big it is
    clean_html = ai_generator.clean_html(html_content)
    
    # Reduce size to 40k to avoid 429
    if len(clean_html) > 40000:
        logger.warning(f"⚠️ HTML still large ({len(clean_html)} chars), slicing to 40k...")
        clean_html = clean_html[:40000]
    
    logger.info(f"✨ Final HTML size for AI: {len(clean_html)} chars")

    prompt = f"""
    Act as a Senior Web Scraper.
    Target URL: {TEST_URL}
    
    Task: Analyze the HTML and find where different variants (e.g., volumes like 30ml, 50ml, 100ml) and their prices are located.
    
    CRITICAL:
    1. Look for a container that REPEATS for each volume option.
    2. Usually it's a list (UL/LI) or a grid of DIVs with class names like 'variant', 'option', 'tiles'.
    3. Return 'null' only if you are absolutely sure no variants exist.
    
    HTML SNIPPET:
    {clean_html}
    
    RETURN JSON: {{ "variant_container": "css", "variant_name": "css", "variant_price": "css" }}
    """

    logger.info("🧠 Sending to Gemini...")
    
    try:
        response = await client.aio.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        logger.success(f"✅ AI Response:\n{response.text}")
    except Exception as e:
        logger.error(f"❌ AI Error: {e}")

if __name__ == "__main__":
    asyncio.run(run_quick_test())
