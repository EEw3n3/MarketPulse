"""Thin Telegram Bot API wrapper using httpx.

Only the two endpoints we need: sendMessage and setWebhook.
Deliberately avoids python-telegram-bot to keep the dependency footprint minimal.
"""
import re
from loguru import logger

from app.core.config import settings

# MarkdownV2 special characters that must be escaped
_MD2_SPECIAL = re.compile(r"([_\*\[\]()~`>#\+\-=|{}.!\\])")


def escape_md(s: str) -> str:
    """Escape a string for Telegram MarkdownV2.

    Every special character must be escaped — e.g. '45.90 €' without escaping
    causes Telegram to return HTTP 400 and the alert is silently lost.
    """
    return _MD2_SPECIAL.sub(r"\\\1", s)


class TelegramBot:
    """Async Telegram Bot API client."""

    _BASE = "https://api.telegram.org/bot{token}/{method}"

    def __init__(self, token: str | None) -> None:
        self._token = token

    def _url(self, method: str) -> str:
        return self._BASE.format(token=self._token, method=method)

    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "MarkdownV2",
    ) -> bool:
        """Send a message. Returns True on success, False on any failure."""
        if not self._token:
            logger.debug("Telegram not configured — skipping send_message")
            return False
        import httpx
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    self._url("sendMessage"),
                    json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
                )
                if not resp.is_success:
                    logger.warning(f"Telegram sendMessage failed: {resp.status_code} {resp.text}")
                    return False
            return True
        except Exception as exc:
            logger.warning(f"Telegram sendMessage error: {exc}")
            return False

    async def set_webhook(self, url: str, secret_token: str | None = None) -> None:
        """Register webhook URL with Telegram."""
        if not self._token:
            return
        import httpx
        payload: dict = {"url": url}
        if secret_token:
            payload["secret_token"] = secret_token
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self._url("setWebhook"), json=payload)
                if resp.is_success:
                    logger.info(f"Telegram webhook registered: {url}")
                else:
                    logger.warning(f"Telegram setWebhook failed: {resp.status_code} {resp.text}")
        except Exception as exc:
            logger.warning(f"Telegram setWebhook error: {exc}")

    async def delete_webhook(self) -> None:
        """Remove any registered webhook."""
        if not self._token:
            return
        import httpx
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(self._url("deleteWebhook"))
        except Exception as exc:
            logger.warning(f"Telegram deleteWebhook error: {exc}")

    async def start_polling(self) -> None:
        """Long-poll getUpdates loop — dev-only fallback when webhook is not available."""
        if not self._token:
            return
        import asyncio
        import httpx
        logger.info("Telegram polling started (dev mode)")
        offset = 0
        while True:
            try:
                async with httpx.AsyncClient(timeout=35) as client:
                    resp = await client.post(
                        self._url("getUpdates"),
                        json={"offset": offset, "timeout": 30},
                    )
                    if not resp.is_success:
                        await asyncio.sleep(5)
                        continue
                    updates = resp.json().get("result", [])
                    for update in updates:
                        offset = update["update_id"] + 1
                        await _handle_update(update)
            except Exception as exc:
                logger.warning(f"Telegram polling error: {exc}")
                await asyncio.sleep(5)


async def _handle_update(update: dict) -> None:
    """Process a single Telegram update (shared by webhook and polling paths)."""
    from app.core.database import async_session
    from app.domain.models import UserPreferences
    from sqlalchemy.future import select
    from datetime import datetime

    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat_id = str(message["chat"]["id"])
    text = (message.get("text") or "").strip()

    if not text.startswith("/start"):
        await bot.send_message(
            chat_id,
            "Open *MarketPulse Settings* to connect your Telegram account\\.",
        )
        return

    # Extract token: "/start mp_<token>"
    parts = text.split(maxsplit=1)
    token_arg = parts[1] if len(parts) > 1 else ""
    if not token_arg.startswith("mp_"):
        await bot.send_message(chat_id, "Open *MarketPulse Settings* to connect your Telegram account\\.")
        return

    raw_token = token_arg[3:]  # strip "mp_" prefix

    async with async_session() as session:
        res = await session.execute(
            select(UserPreferences).where(UserPreferences.telegram_link_token == raw_token)
        )
        prefs = res.scalar_one_or_none()

        if not prefs:
            await bot.send_message(chat_id, "Link not found\\. Generate a new one in Settings\\.")
            return

        if prefs.telegram_link_token_expires_at and prefs.telegram_link_token_expires_at < datetime.utcnow():
            await bot.send_message(chat_id, "Link expired\\. Generate a new one in Settings\\.")
            return

        prefs.telegram_chat_id = chat_id
        prefs.telegram_link_token = None
        prefs.telegram_link_token_expires_at = None
        await session.commit()
        prefs_id = prefs.id

    await bot.send_message(
        chat_id,
        "✅ *Connected\\!* You'll now receive MarketPulse price alerts here\\.",
    )
    logger.info(f"Telegram connected for prefs id={prefs_id} chat_id={chat_id}")


# Module-level singleton
bot = TelegramBot(settings.TELEGRAM_BOT_TOKEN)
