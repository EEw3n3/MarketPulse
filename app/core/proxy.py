import os
import random
from typing import Optional, List, Dict, Union
from loguru import logger
from dotenv import load_dotenv

load_dotenv() 

# Proxy error indicators from Scrapling
_PROXY_ERROR_INDICATORS = {
    "net::err_proxy",
    "net::err_tunnel",
    "connection refused",
    "connection reset",
    "connection timed out",
    "failed to connect",
    "could not resolve proxy",
}

def is_proxy_error(error: Exception) -> bool:
    """Check if an error is proxy-related. Works for both HTTP and browser errors."""
    error_msg = str(error).lower()
    return any(indicator in error_msg for indicator in _PROXY_ERROR_INDICATORS)

class ProxyManager:
    """
    Improved Proxy Manager with error detection inspired by Scrapling.
    Supports both string URLs and potential future dict-based proxies.
    """
    def __init__(self, proxy_list: Optional[List[str]] = None):
        self.proxies = proxy_list or []
        self.bad_proxies = set() # Burnt IPs go here
        self._current_index = 0
        
        # If no proxies passed, try to load from env
        if not self.proxies:
            self._load_from_env()

    def _load_from_env(self):
        proxy_str = os.getenv("PROXY_LIST", "")
        if proxy_str:
            # Supports comma-separated list
            self.proxies = [p.strip() for p in proxy_str.split(",") if p.strip()]
            logger.info(f"🔌 Loaded {len(self.proxies)} proxies from settings.")

    def get_proxy(self) -> Optional[str]:
        """
        Returns the next available proxy in a cyclic manner.
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
        
        # Cyclic rotation instead of just random (more predictable load distribution)
        idx = self._current_index % len(available)
        self._current_index = (idx + 1) % len(available)
        return available[idx]

    def ban_proxy(self, proxy: str):
        """
        Marks proxy as 'burnt' for this session.
        """
        if proxy and proxy in self.proxies:
            logger.warning(f"🔥 Proxy burnt and banned: {proxy}")
            self.bad_proxies.add(proxy)

    def handle_error(self, proxy: str, error: Exception):
        """
        Detects if error was caused by proxy and bans it if necessary.
        """
        if proxy and is_proxy_error(error):
            logger.error(f"🚨 Proxy Error detected for {proxy}: {error}")
            self.ban_proxy(proxy)
            return True
        return False

    def get_stats(self):
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
