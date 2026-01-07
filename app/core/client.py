import asyncio
import random
from curl_cffi.requests import AsyncSession
from loguru import logger
from app.core.proxy import proxy_manager

class StealthClient:
    """
    Улучшенный клиент: использует Keep-Alive (постоянные сессии) 
    и TLS Spoofing для имитации реального браузера.
    """
    IMPERSONATE_TARGETS = ["chrome120", "chrome124", "safari15_5"]
    MAX_RETRIES = 5  # Количество попыток пробить защиту

    def __init__(self):
        self.session = None # Храним сессию здесь
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
        # Получаем новый прокси из менеджера
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
        logger.info(f"🔌 Создана новая Stealth-сессия: {self.current_browser} | {proxy_log}")

    async def get_page(self, url: str):
        """
        Fetches the HTML content of a given URL using the active stealth session.
        Implements automatic retry logic, proxy rotation, and error handling for common bot blocks.
        """
        # Если сессии нет - создаем
        if not self.session:
            await self.init_session()
            
        attempt = 0
        while attempt < self.MAX_RETRIES:
            attempt += 1
            
            # Формируем лог прокси для текущего запроса
            proxy_log = "Direct" if not self.current_proxy else f"Proxy {self.current_proxy.split('@')[-1]}"
            logger.info(f"🕵️‍♂️ [Попытка {attempt}/{self.MAX_RETRIES}] {self.current_browser} | {proxy_log} | Target: {url}")
            
            try:
                response = await self.session.get(url)
                
                # УСПЕХ
                if response.status_code == 200:
                    return response.text
                
                # СТРАНИЦА НЕ НАЙДЕНА
                if response.status_code == 404:
                    logger.warning(f"Страница не найдена (404): {url}")
                    return None

                # БАН ИЛИ ОШИБКА ОЖИДАНИЯ
                if response.status_code in [403, 429, 503]:
                    logger.warning(f"⛔ Блокировка {response.status_code} на {proxy_log}. Баню прокси и меняю сессию...")
                    if self.current_proxy:
                        proxy_manager.ban_proxy(self.current_proxy)
                    
                    # Закрываем текущую сессию и создаем новую (с новым IP и браузером)
                    await self.init_session()
                    await asyncio.sleep(random.uniform(1, 3))
                    continue
                
                logger.warning(f"Странный статус ({response.status_code}) на {proxy_log}")
                return None

            except Exception as e:
                logger.error(f"Network Error ({proxy_log}): {e}")
                # При ошибке сети тоже баним прокси и пересоздаем сессию
                if self.current_proxy:
                    proxy_manager.ban_proxy(self.current_proxy)
                
                await self.init_session()
                await asyncio.sleep(random.uniform(1, 2))
                continue
        
        logger.critical(f"❌ Не удалось пробить защиту после {self.MAX_RETRIES} попыток.")
        return None

    async def close(self):
        if self.session:
            try:
                await self.session.close()
            except:
                pass
            self.session = None

# Глобальный клиент для переиспользования
stealth_client = StealthClient()