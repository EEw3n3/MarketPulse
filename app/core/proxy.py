import os
import random
from typing import Optional, List
from loguru import logger
from dotenv import load_dotenv

load_dotenv() 

PROXY_LIST = os.getenv("PROXY_LIST", "")

class ProxyManager:
    def __init__(self, proxy_list: List[str] = None):
        self.proxies = proxy_list or []
        self.bad_proxies = set() # Сюда кидаем сгоревшие IP
        
        # Если прокси не передали, пробуем загрузить из env или файла
        if not self.proxies:
            self._load_from_env()

    def _load_from_env(self):
        # В продакшене список прокси будет длинным, берем из переменной окружения
        # Формат: "http://user:pass@ip:port,http://user:pass@ip:port"
        proxy_str = os.getenv("PROXY_LIST", "")
        if proxy_str:
            self.proxies = [p.strip() for p in proxy_str.split(",")]
            logger.info(f"🔌 Загружено {len(self.proxies)} прокси из настроек.")

    def get_proxy(self) -> Optional[str]:
        """
        Возвращает случайный живой прокси.
        """
        available = [p for p in self.proxies if p not in self.bad_proxies]
        
        if not available:
            if not self.proxies:
                return None # Работаем без прокси (Direct)
            else:
                # Если все прокси "сгорели", обнуляем бан-лист (Desperate mode)
                logger.warning("♻️ Все прокси помечены как плохие. Сброс цикла ротации.")
                self.bad_proxies.clear()
                available = self.proxies
        
        return random.choice(available)

    def ban_proxy(self, proxy: str):
        """
        Помечает прокси как 'сгоревший' на эту сессию.
        """
        if proxy:
            logger.warning(f"🔥 Прокси сожжен и убран в бан: {proxy}")
            self.bad_proxies.add(proxy)

    def get_stats(self):
        """
        Метод для отладки: показывает состояние пула прокси.
        """
        total = len(self.proxies)
        banned = len(self.bad_proxies)
        active = total - banned
        return {
            "Total": total,
            "Active": active,
            "Banned": banned,
            "Banned_List": list(self.bad_proxies)
        }

# Глобальный инстанс
proxy_manager = ProxyManager()