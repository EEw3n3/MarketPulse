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
        """Starts Playwright and the browser.

        Strategy: prefer the user's real installed Chrome via channel="chrome".
        Real Chrome has the full plugin/font/codec footprint, correct TLS+JA3
        fingerprint, and clean WebGL/Audio context output — none of which the
        bundled chromium replicates. Cloudflare Managed Challenge (1a.lv) is
        very effective at flagging bundled headless chromium even with stealth
        patches; using real Chrome gets us past it in practice.

        Falls back to bundled chromium if Chrome isn't installed (e.g. server
        without GUI). Falls back to headless if non-headless fails (no display).
        """
        async with self.lock:
            if self.playwright:
                return
            self.playwright = await async_playwright().start()

            base_args = [
                "--disable-blink-features=AutomationControlled",  # hide "controlled by automation"
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]

            # Try real Chrome non-headless first (best stealth posture)
            launch_attempts = [
                {"channel": "chrome", "headless": False, "args": base_args, "label": "real Chrome (headed)"},
                {"channel": "chrome", "headless": True,  "args": base_args, "label": "real Chrome (headless)"},
                {"headless": True, "args": base_args, "label": "bundled chromium (headless)"},
            ]

            last_err: Exception | None = None
            for cfg in launch_attempts:
                label = cfg.pop("label")
                try:
                    self.browser = await self.playwright.chromium.launch(**cfg)
                    logger.info(f"🚜 Tier 3: Browser Engine started — {label}")
                    return
                except Exception as e:
                    last_err = e
                    logger.warning(f"Browser launch failed ({label}): {e}")

            raise RuntimeError(f"All browser launch attempts failed. Last error: {last_err}")

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
            proxy=proxy_config,
            locale="lv-LV",            # Latvian locale matches our target sites
            timezone_id="Europe/Riga",  # matches LV-LV
        )

        # ── Stealth init script ──────────────────────────────────────────────
        # Runs in every page BEFORE site JS executes. We patch the most common
        # bot tells that Cloudflare/DataDome/PerimeterX use to fingerprint
        # automation:
        #   - navigator.webdriver         → undefined (was true)
        #   - navigator.plugins           → fake 3-plugin list (was empty)
        #   - navigator.languages         → ["lv-LV", "lv", "en-US", "en"]
        #   - window.chrome               → fake runtime object (missing in HL)
        #   - WebGL UNMASKED_VENDOR/RENDERER → Intel/Iris instead of SwiftShader
        await context.add_init_script("""
            // Hide webdriver
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

            // Fake plugin list — empty plugins is a huge red flag
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                    { name: 'Native Client', filename: 'internal-nacl-plugin' },
                ],
            });

            // Languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['lv-LV', 'lv', 'en-US', 'en'],
            });

            // window.chrome runtime
            if (!window.chrome) {
                window.chrome = { runtime: {}, app: {}, csi: () => {}, loadTimes: () => {} };
            }

            // Permissions API: notifications should be 'default', not 'denied'
            const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
            if (originalQuery) {
                window.navigator.permissions.query = (parameters) =>
                    parameters.name === 'notifications'
                        ? Promise.resolve({ state: Notification.permission })
                        : originalQuery(parameters);
            }

            // WebGL vendor/renderer spoof — bundled chromium returns
            // 'Google Inc. (Google)' / 'ANGLE (Google, SwiftShader, ...)' which is a tell.
            const getParameterProxy = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(param) {
                if (param === 37445) return 'Intel Inc.';                            // UNMASKED_VENDOR_WEBGL
                if (param === 37446) return 'Intel(R) Iris(TM) Plus Graphics 640';   // UNMASKED_RENDERER_WEBGL
                return getParameterProxy.apply(this, [param]);
            };
        """)

        return context

    # Phrases CF uses across Turnstile / Managed Challenge / I'm Under Attack pages.
    # We check the rendered page text for ANY of these to decide whether we're still
    # behind a challenge. Multiple variants because CF rotates wording per challenge type.
    __CF_CHALLENGE_PHRASES__ = (
        "Just a moment...",
        "Verifying you are human",
        "Checking your browser",
        "Please verify you are a human",
        "needs to review the security",
        "Performance & security by Cloudflare",
        "Verify you are human",
    )

    async def _challenge_still_present(self, page: Page) -> bool:
        try:
            content = await page.content()
        except Exception:
            return True  # if we can't read content, assume still challenged
        return any(phrase in content for phrase in self.__CF_CHALLENGE_PHRASES__)

    async def _solve_cloudflare(self, page: Page) -> bool:
        """
        Attempts to pass a Cloudflare interstitial (Turnstile / Managed Challenge).

        Strategy, in order:
          1. Wait up to 15s for the challenge to auto-pass (some Managed Challenges
             clear themselves once Cloudflare finishes silent JS verification).
          2. If still blocked, locate the Turnstile iframe and human-click the
             checkbox: real mouse movement to the click point, randomized offset,
             slight pause, then click.
          3. Wait up to 25s for the page text to lose every challenge phrase we
             know about.

        Returns True when the page is usable (no challenge OR challenge cleared),
        False when a challenge is still present after we've exhausted our attempts.
        Callers can use False as a signal to reload and re-try.
        """
        try:
            if not await self._challenge_still_present(page):
                return True  # page is already clean

            logger.info("🛡️ Cloudflare challenge detected. Attempting to solve…")

            # ── Step 1: passive wait — many Managed Challenges auto-resolve ────────
            for _ in range(15):
                await asyncio.sleep(1)
                if not await self._challenge_still_present(page):
                    logger.success("✅ Cloudflare challenge auto-resolved (no click needed).")
                    return True

            # ── Step 2: locate Turnstile iframe ────────────────────────────────────
            import re
            iframe = None
            for attempt in range(12):
                for frame in page.frames:
                    if re.match(self.__CF_PATTERN__, frame.url):
                        iframe = frame
                        break
                if iframe:
                    logger.info(f"🛡️ Turnstile iframe found after auto-wait + {attempt}s")
                    break
                await asyncio.sleep(1)

            if not iframe:
                logger.warning("⚠️ Cloudflare iframe not found after passive wait.")
                return False  # caller may reload and re-try

            # ── Step 3: human-like click on checkbox ──────────────────────────────
            try:
                frame_element = await iframe.frame_element()
                if not frame_element:
                    return False
                try:
                    await frame_element.scroll_into_view_if_needed(timeout=3000)
                except Exception:
                    pass

                box = await frame_element.bounding_box()
                if not box:
                    return False

                # Turnstile checkbox sits ~30px from iframe top-left. Jitter to look human.
                click_x = box["x"] + random.randint(25, 32)
                click_y = box["y"] + random.randint(25, 32)

                # Move the mouse to a random idle position first, then trace to the
                # click point in steps. CF's interaction-detector flags teleport-clicks.
                start_x = box["x"] + box["width"] + random.randint(50, 200)
                start_y = box["y"] + random.randint(-50, 50)
                await page.mouse.move(start_x, start_y)
                await asyncio.sleep(random.uniform(0.3, 0.7))
                await page.mouse.move(click_x, click_y, steps=random.randint(15, 25))
                await asyncio.sleep(random.uniform(0.15, 0.35))

                logger.info(f"👆 Clicking Turnstile at ({click_x:.0f}, {click_y:.0f})")
                await page.mouse.click(click_x, click_y, delay=random.randint(80, 180))

                # ── Step 4: wait for resolution (longer window) ───────────────────
                for _ in range(25):
                    await asyncio.sleep(1)
                    if not await self._challenge_still_present(page):
                        logger.success("✅ Cloudflare challenge solved!")
                        return True

                logger.warning("⚠️ Cloudflare challenge still present after click + 25s wait.")
            except Exception as e:
                logger.error(f"❌ Error during CF solving: {e}")

            return False
        except Exception:
            return False

    # Present on every real notino.lv catalog / product page, never on the
    # Cloudflare interstitial.
    NOTINO_CONTENT = ("[data-testid='product-container'], [data-testid='pd-price-wrapper'], "
                      "[data-testid='price-component'], #pdVariantsTile, #pdVariantsThumbnail")

    async def wait_for_notino_content(self, page: Page, timeout_ms: int = 25000) -> bool:
        """Wait for the real notino.lv page. Notino sometimes answers with a
        Cloudflare interstitial ("Mazliet uzgaidiet…") that passes by itself
        after a few seconds; this only waits for it and never answers a check.
        False means the page did not load — the caller must not treat the
        interstitial as data."""
        try:
            await page.wait_for_selector(self.NOTINO_CONTENT, state="attached", timeout=timeout_ms)
            return True
        except Exception:
            logger.warning(f"⚠️ notino.lv page did not load (Cloudflare check did not pass by itself): {page.url}")
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
                cf_ok = await self._solve_cloudflare(page)
                if not cf_ok:
                    # CF often lets you through on the second hit because the first
                    # navigation set the cf_clearance / cf_chl_* cookies — reload
                    # the page once and try the solver again.
                    logger.info("🔁 Reloading page to retry Cloudflare challenge…")
                    try:
                        await page.reload(wait_until="domcontentloaded", timeout=60000)
                    except Exception as e:
                        logger.warning(f"Reload failed during CF retry: {e}")
                    cf_ok = await self._solve_cloudflare(page)
                    if not cf_ok:
                        logger.error("❌ Cloudflare still blocking after reload + retry.")

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
            elif "notino.lv" in url:
                await self.wait_for_notino_content(page)

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