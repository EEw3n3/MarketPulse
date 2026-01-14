import asyncio
import random
from curl_cffi.requests import AsyncSession
from loguru import logger
from app.core.proxy import proxy_manager

class StealthClient:
    """
    Enhanced client: uses Keep-Alive (persistent sessions)
    and TLS Spoofing to mimic a real browser.
    """
    IMPERSONATE_TARGETS = ["chrome120", "chrome124", "safari15_5"]
    MAX_RETRIES = 5  # Number of attempts to bypass protection

    def __init__(self):
        self.session = None # Store session here
        self.current_browser = None
        self.current_proxy = None

    async def init_session(self):
        """
        Initializes a long-lived HTTP session with Keep-Alive support.
        Configures TLS spoofing (impersonation) and rotates proxies to bypass bot detection.
        """
        if self.session:
            await self.close()
            
        self.current_browser = random.choice(self.IMPERSONATE_TARGETS)
        # Get new proxy from manager
        self.current_proxy = proxy_manager.get_proxy()
        proxies = {"http": self.current_proxy, "https": self.current_proxy} if self.current_proxy else None
        
        self.session = AsyncSession(
            impersonate=self.current_browser,
            proxies=proxies,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
                "Cache-Control": "no-cache",
            },
            timeout=30
        )
        proxy_log = "Direct" if not self.current_proxy else f"Proxy {self.current_proxy.split('@')[-1]}"
        logger.info(f"🔌 New Stealth session created: {self.current_browser} | {proxy_log}")

    async def get_page(self, url: str):
        """
        Fetches the HTML content of a given URL using the active stealth session.
        Implements automatic retry logic, proxy rotation, and error handling for common bot blocks.
        """
        # If no session - create it
        if not self.session:
            await self.init_session()
            
        attempt = 0
        while attempt < self.MAX_RETRIES:
            attempt += 1
            
            # Form proxy log for current request
            proxy_log = "Direct" if not self.current_proxy else f"Proxy {self.current_proxy.split('@')[-1]}"
            logger.info(f"🕵️‍♂️ [Attempt {attempt}/{self.MAX_RETRIES}] {self.current_browser} | {proxy_log} | Target: {url}")
            
            try:
                response = await self.session.get(url)
                
                # SUCCESS
                if response.status_code == 200:
                    return response.text
                
                # PAGE NOT FOUND
                if response.status_code == 404:
                    logger.warning(f"Page not found (404): {url}")
                    return None

                # BAN OR TIMEOUT ERROR
                if response.status_code in [403, 429, 503]:
                    logger.warning(f"⛔ Blocking {response.status_code} on {proxy_log}. Banning proxy and changing session...")
                    if self.current_proxy:
                        proxy_manager.ban_proxy(self.current_proxy)
                    
                    # Close current session and create new one (with new IP and browser)
                    await self.init_session()
                    await asyncio.sleep(random.uniform(1, 3))
                    continue
                
                logger.warning(f"Strange status ({response.status_code}) on {proxy_log}")
                return None

            except Exception as e:
                logger.error(f"Network Error ({proxy_log}): {e}")
                # On network error also ban proxy and recreate session
                if self.current_proxy:
                    proxy_manager.ban_proxy(self.current_proxy)
                
                await self.init_session()
                await asyncio.sleep(random.uniform(1, 2))
                continue
        
        logger.critical(f"❌ Failed to bypass protection after {self.MAX_RETRIES} attempts.")
        return None

    async def close(self):
        if self.session:
            try:
                await self.session.close()
            except:
                pass
            self.session = None

# Global client for reuse
stealth_client = StealthClient()