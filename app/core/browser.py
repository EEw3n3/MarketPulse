import asyncio
import random
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from playwright_stealth import stealth_async  # <-- IMPORTANT: Stealth patch
from loguru import logger
from app.core.proxy import proxy_manager
from app.core.humanizer import Humanizer # <-- Our new module

class NetworkInterceptor:
    def __init__(self):
        self.intercepted_responses = []
        self.intercepted_requests = []

    async def handle_response(self, response):
        try:
            if "application/json" in response.headers.get("content-type", "").lower():
                url = response.url
                # убрали фильтр на слова tracking, events, чтобы ловить те самые Payload, о которых ты говорил
                junk = ['google', 'facebook', 'hotjar', 'metrics', 'clarity', 'trustpilot', 'doubleclick', 'ads']
                if any(j in url.lower() for j in junk):
                    return
                json_data = await response.json()
                self.intercepted_responses.append({"url": url, "data": json_data})
        except Exception as e:
            pass

    async def handle_request(self, request):
        try:
            url = request.url
            junk = ['google', 'facebook', 'hotjar', 'metrics', 'clarity', 'trustpilot', 'doubleclick', 'ads']
            if any(j in url.lower() for j in junk):
                return
            
            if request.method in ["POST", "PUT", "PATCH"]:
                post_data = request.post_data_json
                if post_data:
                    self.intercepted_requests.append({"url": url, "data": post_data})
        except Exception as e:
            pass


class BrowserManager:
    # Cloudflare Turnstile iframes load from the `challenges.cloudflare.com`
    # subdomain (NOT the apex `cloudflare.com`). Earlier we matched only the
    # apex, so the solver always logged "iframe not found" on sites like 1a.lv
    # and gave up. Match any cloudflare.com subdomain to be safe.
    __CF_PATTERN__ = r"^https?://(?:[\w-]+\.)?cloudflare\.com/.*challenge.*"

    def __init__(self) -> None:
        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.lock = asyncio.Lock()

    async def start(self):
        """Starts Playwright and the browser"""
        async with self.lock:
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

    async def _solve_cloudflare(self, page: Page) -> bool:
        """
        Attempts to solve Cloudflare Turnstile challenge using coordinate-based clicking.
        Inspired by Scrapling logic.
        """
        try:
            # Check if CF challenge is present
            content = await page.content()
            if "Just a moment..." not in content and "Verifying you are human" not in content:
                return False

            logger.info("🛡️ Cloudflare challenge detected. Attempting to solve...")

            # Turnstile iframe can take 3-8 seconds to spawn after the page loads.
            # Poll for up to ~12s instead of a single 2-second sleep — the old
            # code consistently lost the race on slower sites like 1a.lv.
            import re
            iframe = None
            for attempt in range(12):
                await asyncio.sleep(1)
                for frame in page.frames:
                    if re.match(self.__CF_PATTERN__, frame.url):
                        iframe = frame
                        break
                if iframe:
                    logger.info(f"🛡️ Turnstile iframe found after {attempt + 1}s")
                    break

            if not iframe:
                logger.warning("⚠️ Cloudflare iframe not found.")
                return False

            # Ensure iframe is visible and get bounding box
            try:
                # We know iframe is not None here
                frame_element = await iframe.frame_element()
                if not frame_element: return False
                
                box = await frame_element.bounding_box()
                if not box: return False
                
                # Turnstile checkbox is usually in the top-left area
                # Scrapling offsets: X + 27, Y + 26
                click_x = box["x"] + random.randint(25, 30)
                click_y = box["y"] + random.randint(25, 30)
                
                logger.info(f"👆 Clicking Turnstile at ({click_x}, {click_y})")
                await page.mouse.click(click_x, click_y, delay=random.randint(100, 200))
                
                # Wait for the challenge to resolve
                for _ in range(10):
                    await asyncio.sleep(1)
                    if "Just a moment..." not in await page.content():
                        logger.success("✅ Cloudflare challenge solved!")
                        return True
            except Exception as e:
                logger.error(f"❌ Error during CF solving: {e}")
                
            return False
        except Exception:
            return False

    async def get_page_content(
        self, 
        url: str, 
        fast_mode: bool = False, 
        disable_images: bool = True, 
        context: BrowserContext | None = None, 
        click_selector: str | None = None, 
        verified_domain: bool = False,
        intercept_traffic: bool = False,
        solve_cf: bool = True
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

            interceptor = None
            if intercept_traffic:
                interceptor = NetworkInterceptor()
                page.on("response", interceptor.handle_response)
                page.on("request", interceptor.handle_request)

            await stealth_async(page)
            
            if fast_mode and not verified_domain: 
                await asyncio.sleep(random.uniform(0.5, 2.0))

            logger.info(f"🚜 Loading page ({'Turbo' if fast_mode else 'Stealth'}): {url}")
            # 220.lv is a React SPA: ?page=N products are fetched client-side after
            # domcontentloaded, so widget-data attributes only appear after networkidle.
            _wait_until = "networkidle" if "220.lv" in url else "domcontentloaded"
            response = await page.goto(url, wait_until=_wait_until, timeout=60000)
            
            # === CLOUDFLARE SOLVER ===
            if solve_cf:
                await self._solve_cloudflare(page)

            # === AUTO-CONSENT (Cookies) ===
            try:
                cookie_selectors = [
                    "button:has-text('Piekrītu')",
                    "button:has-text('Apstiprināt')",
                    "button:has-text('Piekrist visiem')",
                    "button:has-text('Pieņemt')",
                    "button:has-text('Pieņemt visu')",
                    "button:has-text('Accept')",
                    "button:has-text('Allow all')",
                    "button:has-text('I agree')",
                    "#onetrust-accept-btn-handler",
                    ".cookie-consent-accept"
                ]
                for btn_sel in cookie_selectors:
                    btn = page.locator(btn_sel).first
                    if await btn.is_visible(timeout=500):
                        await btn.click()
                        logger.info(f"🍪 Auto-accepted cookies using: {btn_sel}")
                        await asyncio.sleep(0.5)
                        break
            except Exception:
                pass
            # UserCentrics CMP (Notino) — lives in shadow DOM, remove overlay directly.
            try:
                removed = await page.evaluate("""() => {
                    const el = document.querySelector('#usercentrics-cmp-ui');
                    if (el) { el.remove(); return true; }
                    return false;
                }""")
                if removed:
                    logger.info("🍪 Removed UserCentrics CMP overlay.")
            except Exception:
                pass
            
            # === CLICK LOGIC ===
            if click_selector:
                logger.info(f"👆 Clicking element: {click_selector}")
                try:
                    # SPA sites (Notino, 220.lv): React renders AFTER domcontentloaded.
                    # Wait for networkidle OR fixed sleep, then ALWAYS add 4s extra
                    # to ensure React hydration is complete before we look for elements.
                    try:
                        await page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        pass
                    await asyncio.sleep(4.0)  # React hydration buffer
                    # state='attached' — element just needs to be in DOM.
                    # 'visible' fails when CSS uses custom properties for visibility.
                    await page.wait_for_selector(click_selector, state="attached", timeout=15000)
                    locator = page.locator(click_selector).first
                    await locator.scroll_into_view_if_needed(timeout=5000)
                    await asyncio.sleep(0.5)
                    await locator.click(force=True, timeout=8000)
                    # Wait for new page content to load
                    try:
                        await page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        await asyncio.sleep(3.0)
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
            
            # Wait for dynamic content (React fragments, SPA hydration, etc.)
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            # 220.lv: CF JS-challenge triggers a meta-refresh redirect that completes
            # AFTER networkidle fires. Wait for actual product cards to appear so we
            # capture the real page, not the challenge page.
            if "220.lv" in url:
                try:
                    await page.wait_for_selector("div.c-product-card[widget-data]", timeout=25000)
                except Exception:
                    pass  # No cards (empty category or still blocked — caller handles)

            final_url = page.url
            content = await page.content()

            if len(content) < 30000:
                short_head = content[:200].replace("\n", " ")
                logger.warning(f"⚠️ Unusual HTML length: {len(content)} bytes. Head: {short_head}")
            
            result = {"html": content, "url": final_url}
            if intercept_traffic and interceptor:
                result["network_data"] = {
                    "requests": interceptor.intercepted_requests,
                    "responses": interceptor.intercepted_responses
                }
            
            # Return both content and the final URL (in case redirects or clicks happened)
            return result

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
        async with self.lock:
            if self.browser:
                await self.browser.close()
                self.browser = None
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None

browser_manager = BrowserManager()