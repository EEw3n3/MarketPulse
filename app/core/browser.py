import asyncio
import random
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from playwright_stealth import stealth_async  # <-- IMPORTANT: Stealth patch
from loguru import logger
from app.core.proxy import proxy_manager
from app.core.humanizer import Humanizer # <-- Our new module

class BrowserManager:
    def __init__(self) -> None:
        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.lock = asyncio.Lock()

    async def start(self):
        """Starts Playwright and the browser"""
        if not self.playwright:
            self.playwright = await async_playwright().start()
            # Running in headless=True for the server, but with arguments hiding it
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled", # Hides "controlled by automation"
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu" 
                ]
            )
            logger.info("🚜 Tier 3: Browser Engine (Chromium) started.")

    async def get_context(self) -> BrowserContext:
        """Creates and returns a new browser context with stealth and human-like settings."""
        if not self.browser:
            await self.start()
            
        assert self.browser is not None, "Browser Engine failed to start."
            
        proxy_str = proxy_manager.get_proxy()
        proxy_config = None
        if proxy_str:
            try:
                protocol, rest = proxy_str.split("://")
                creds, addr = rest.split("@")
                username, password = creds.split(":")
                proxy_config = {
                    "server": f"{protocol}://{addr}",
                    "username": username,
                    "password": password
                }
            except Exception:
                proxy_config = {"server": proxy_str}

        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        
        viewports = [
            {"width": 1920, "height": 1080},
            {"width": 1366, "height": 768},
            {"width": 1536, "height": 864},
            {"width": 1440, "height": 900}
        ]

        context = await self.browser.new_context(
            user_agent=random.choice(user_agents),
            viewport=random.choice(viewports),
            proxy=proxy_config
        )
        return context

    async def get_page_content(
        self, 
        url: str, 
        fast_mode: bool = False, 
        disable_images: bool = True, 
        context: BrowserContext | None = None, 
        click_selector: str | None = None, 
        verified_domain: bool = False
    ) -> dict | None:
        """
        Opens the page, potentially clicks a selector, and returns HTML + Final URL.
        - click_selector: CSS selector to click after loading (e.g. "next page" button)
        - verified_domain: if True, skip humanizing delays (saves 3-5s per verified domain page)
        """
        if not self.browser:
            await self.start()
            
        assert self.browser is not None, "Browser Engine failed to start."

        # ... (context creation logic remains same) ...
        local_context = context
        if not local_context:
            local_context = await self.get_context()
        
        page: Page | None = None 
        try:
            page = await local_context.new_page()

            if disable_images:
                await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,ico}", lambda route: route.abort())

            await stealth_async(page)
            
            if fast_mode and not verified_domain: 
                await asyncio.sleep(random.uniform(0.5, 2.0))

            logger.info(f"🚜 Loading page ({'Turbo' if fast_mode else 'Stealth'}): {url}")
            response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # === CLICK LOGIC ===
            if click_selector:
                logger.info(f"👆 Clicking element: {click_selector}")
                try:
                    await page.wait_for_selector(click_selector, timeout=5000)
                    await page.click(click_selector)
                    # Wait for navigation or AJAX
                    try:
                        await page.wait_for_load_state("networkidle", timeout=8000)
                    except Exception: 
                        await asyncio.sleep(3.0) # Fallback wait
                except Exception as e:
                    logger.warning(f"⚠️ Click failed for {click_selector}: {e}")

            status = response.status if response else "Unknown"
            logger.debug(f"🌐 Response status: {status} for {url}")

            # === TIER 4: HUMAN BEHAVIOR ===
            if verified_domain:
                # Verified domains: no anti-bot, skip humanizing. Just wait for JS render.
                await asyncio.sleep(random.uniform(0.3, 0.7))
            elif fast_mode:
                # Unknown domain in Turbo mode: minimal human sim
                await asyncio.sleep(random.uniform(3.0, 5.0))
                await page.mouse.move(random.randint(100, 800), random.randint(100, 800))
                await page.mouse.wheel(0, random.randint(100, 300))
            else:
                logger.info("🤖 Simulating human (Humanizing)...")
                await Humanizer.smart_wait(2, 4)
                await Humanizer.random_mouse_move(page)
                await Humanizer.human_scroll(page)
                await Humanizer.smart_wait(2, 4)

            # === INTERACTIVE ACTIONS (e.g. Pagination Click) ===
            # If we need to perform actions before capturing content
            # Accepts a dict: {"action": "click", "selector": ".btn"}
            
            # Since we can't easily pass complex objects, we'll rely on the caller to handle complex flows
            # But for simple pagination clicks, we can add a helper arg in future.
            
            # Wait for any dynamic content
            try:
                if fast_mode:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                else:
                    await page.wait_for_load_state("domcontentloaded")
            except Exception:
                pass

            final_url = page.url
            content = await page.content()
            
            if len(content) < 30000:
                short_head = content[:200].replace("\n", " ")
                logger.warning(f"⚠️ Unusual HTML length: {len(content)} bytes. Head: {short_head}")
            
            # Return both content and the final URL (in case redirects or clicks happened)
            return {"html": content, "url": final_url}

        except Exception as e:
            logger.error(f"❌ Browser error: {e}")
            return None
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
            
            # If we didn't provide a context (so we created a local one), we must close it.
            if not context and local_context:
                try:
                    await local_context.close()
                except Exception:
                    pass

    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

browser_manager = BrowserManager()