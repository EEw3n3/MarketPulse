import asyncio
import random
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from playwright_stealth import stealth_async  # <-- IMPORTANT: Stealth patch
from loguru import logger
from app.core.config import settings
from app.core.proxy import proxy_manager
from app.core.humanizer import Humanizer # <-- Our new module

class BrowserManager:
    def __init__(self):
        self.playwright = None
        self.browser = None
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

    async def get_page_content(self, url: str, fast_mode: bool = False, disable_images: bool = True, context: BrowserContext = None) -> str | None:
        """
        Opens the page, pretends to be human, scrolls, and returns HTML.
        - fast_mode: Reduces pauses for pagination
        - disable_images: Blocks image loading to save time/bandwidth
        - context: Optional existing context to reuse browser session
        """
        if not self.browser:
            await self.start()

        # 2. Use existing or create new context
        local_context = context if context else await self.get_context()
        
        page = await local_context.new_page()

        # === OPTIMIZATION: BLOATING KILLER ===
        if disable_images:
            await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,ico}", lambda route: route.abort())

        try:
            # === TIER 4: STEALTH INJECTION ===
            await stealth_async(page)
            
            # Staggered start to avoid hitting the server at the exact same ms in parallel batches
            if fast_mode: 
                await asyncio.sleep(random.uniform(0.5, 2.0))

            logger.info(f"🚜 Loading page ({'Turbo' if fast_mode else 'Stealth'}): {url}")
            response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            status = response.status if response else "Unknown"
            logger.debug(f"🌐 Response status: {status} for {url}")

            # === TIER 4: HUMAN BEHAVIOR ===
            if fast_mode:
                # Wait longer for heavy JS sites like Notino
                await asyncio.sleep(random.uniform(3.0, 5.0))
                await page.mouse.move(random.randint(100, 800), random.randint(100, 800))
                await page.mouse.wheel(0, random.randint(100, 300))
            else:
                logger.info("🤖 Simulating human (Humanizing)...")
                await Humanizer.smart_wait(2, 4)
                await Humanizer.random_mouse_move(page)
                await Humanizer.human_scroll(page)
                await Humanizer.smart_wait(2, 4)

            content = await page.content()
            
            if len(content) < 30000:
                logger.warning(f"⚠️ Unusual HTML length: {len(content)} bytes. Head: {content[:200].replace('\n', ' ')}")
            
            return content

        except Exception as e:
            logger.error(f"❌ Browser error: {e}")
            return None
        finally:
            await page.close()
            # If we didn't provide a context, we should close the one we created locally
            if not context:
                await local_context.close()

    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

browser_manager = BrowserManager()