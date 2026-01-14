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
        self.bad_proxies = set() # Burnt IPs go here
        
        # If no proxies passed, try to load from env or file
        if not self.proxies:
            self._load_from_env()

    def _load_from_env(self):
        # In production proxy list will be long, take from environment variable
        # Format: "http://user:pass@ip:port,http://user:pass@ip:port"
        proxy_str = os.getenv("PROXY_LIST", "")
        if proxy_str:
            self.proxies = [p.strip() for p in proxy_str.split(",")]
            logger.info(f"🔌 Loaded {len(self.proxies)} proxies from settings.")

    def get_proxy(self) -> Optional[str]:
        """
        Returns a random alive proxy.
        """
        available = [p for p in self.proxies if p not in self.bad_proxies]
        
        if not available:
            if not self.proxies:
                return None # Working without proxy (Direct)
            else:
                # If all proxies are "burnt", reset ban list (Desperate mode)
                logger.warning("♻️ All proxies marked as bad. Rotation cycle reset.")
                self.bad_proxies.clear()
                available = self.proxies
        
        return random.choice(available)

    def ban_proxy(self, proxy: str):
        """
        Marks proxy as 'burnt' for this session.
        """
        if proxy:
            logger.warning(f"🔥 Proxy burnt and banned: {proxy}")
            self.bad_proxies.add(proxy)

    def get_stats(self):
        """
        Debug method: shows proxy pool state.
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

# Global instance
proxy_manager = ProxyManager()