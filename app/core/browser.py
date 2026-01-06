import asyncio
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from playwright_stealth import stealth_async  # <-- ВАЖНО: Stealth патч
from loguru import logger
from app.core.config import settings
from app.core.proxy import proxy_manager
from app.core.humanizer import Humanizer # <-- Наш новый модуль

class BrowserManager:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.lock = asyncio.Lock()

    async def start(self):
        """Запускает Playwright и браузер"""
        if not self.playwright:
            self.playwright = await async_playwright().start()
            # Запускаем в headless=True для сервера, но с аргументами, скрывающими это
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled", # Скрывает "controlled by automation"
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu" 
                ]
            )
            logger.info("🚜 Tier 3: Browser Engine (Chromium) started.")

    async def get_page_content(self, url: str) -> str | None:
        """
        Открывает страницу, притворяется человеком, скроллит и возвращает HTML.
        """
        if not self.browser:
            await self.start()

        # 1. Получаем прокси
        proxy_str = proxy_manager.get_proxy()
        proxy_config = None
        if proxy_str:
            # Превращаем http://user:pass@ip:port в конфиг для Playwright
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
                # Если прокси без пароля или кривой формат
                proxy_config = {"server": proxy_str}

        # 2. Создаем контекст (изолированную сессию)
        # Подменяем User-Agent на реальный
        context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            proxy=proxy_config
        )
        
        page = await context.new_page()

        try:
            # === TIER 4: STEALTH INJECTION ===
            # Скрываем признаки Selenium/Playwright
            await stealth_async(page)
            
            logger.info(f"🚜 Загружаю страницу (Stealth Mode): {url}")
            # Увеличиваем таймаут до 60 сек, так как мы будем "тупить" как человек
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # === TIER 4: HUMAN BEHAVIOR ===
            logger.info("🤖 Имитация человека (Humanizing)...")
            
            # 1. Случайная пауза перед действием
            await Humanizer.smart_wait(1, 3)
            
            # 2. Двигаем мышкой "в никуда", чтобы сбить трекеры
            await Humanizer.random_mouse_move(page)
            
            # 3. Скроллим страницу (это триггерит подгрузку товаров на Nike!)
            await Humanizer.human_scroll(page)
            
            # 4. Финальная пауза, чтобы убедиться, что JS отработал
            await Humanizer.smart_wait(2, 4)

            content = await page.content()
            return content

        except Exception as e:
            logger.error(f"❌ Ошибка браузера: {e}")
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