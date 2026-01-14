import asyncio
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

    async def get_page_content(self, url: str) -> str | None:
        """
        Opens the page, pretends to be human, scrolls, and returns HTML.
        """
        if not self.browser:
            await self.start()

        # 1. Get proxy
        proxy_str = proxy_manager.get_proxy()
        proxy_config = None
        if proxy_str:
            # Convert http://user:pass@ip:port into Playwright config
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
                # If proxy is without password or has invalid format
                proxy_config = {"server": proxy_str}

        # 2. Create context (isolated session)
        # Spoof User-Agent to a real one
        context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            proxy=proxy_config
        )
        
        page = await context.new_page()

        try:
            # === TIER 4: STEALTH INJECTION ===
            # Hide Selenium/Playwright signs
            await stealth_async(page)
            
            logger.info(f"🚜 Loading page (Stealth Mode): {url}")
            # Increase timeout to 60s, as we will "loaf around" like a human
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # === TIER 4: HUMAN BEHAVIOR ===
            logger.info("🤖 Simulating human (Humanizing)...")
            
            # 1. Random pause before action
            await Humanizer.smart_wait(1, 3)
            
            # 2. Move mouse "nowhere" to confuse trackers
            await Humanizer.random_mouse_move(page)
            
            # 3. Scroll the page (this triggers product loading on Nike!)
            await Humanizer.human_scroll(page)
            
            # 4. Final pause to ensure JS execution
            await Humanizer.smart_wait(2, 4)

            content = await page.content()
            return content

        except Exception as e:
            logger.error(f"❌ Browser error: {e}")
            return None
        finally:
            await page.close()
            await context.close()

    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

browser_manager = BrowserManager()