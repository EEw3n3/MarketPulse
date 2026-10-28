"""Telegram integration endpoints.

POST /auth/telegram/connect    — generate deep-link token
POST /auth/telegram/disconnect — clear chat_id
POST /auth/telegram/webhook    — receive Telegram updates (always returns 200)
"""
import hmac
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import schemas
from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.domain.models import User, UserPreferences
from app.services.telegram_bot import _handle_update
from sqlalchemy.future import select

router = APIRouter(prefix="/auth/telegram", tags=["telegram"])

_TOKEN_TTL_HOURS = 24


async def _get_or_create_prefs(db: AsyncSession, user_id: int) -> UserPreferences:
    res = await db.execute(select(UserPreferences).where(UserPreferences.user_id == user_id))
    prefs = res.scalar_one_or_none()
    if not prefs:
        prefs = UserPreferences(user_id=user_id)
        db.add(prefs)
        await db.flush()
    return prefs


@router.post("/connect", response_model=schemas.TelegramConnectResponse)
async def connect_telegram(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.TelegramConnectResponse:
    """Generate a one-time deep-link token for Telegram verification."""
    prefs = await _get_or_create_prefs(db, user.id)

    token = secrets.token_urlsafe(24)
    expires_at = datetime.utcnow() + timedelta(hours=_TOKEN_TTL_HOURS)

    prefs.telegram_link_token = token
    prefs.telegram_link_token_expires_at = expires_at
    await db.commit()

    bot_username = settings.TELEGRAM_BOT_USERNAME
    deep_link = f"https://t.me/{bot_username}?start=mp_{token}"

    return schemas.TelegramConnectResponse(deep_link=deep_link, expires_at=expires_at)


@router.post("/disconnect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_telegram(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Clear Telegram chat_id — user will stop receiving Telegram alerts."""
    prefs = await _get_or_create_prefs(db, user.id)
    prefs.telegram_chat_id = None
    prefs.telegram_link_token = None
    prefs.telegram_link_token_expires_at = None
    await db.commit()


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    """Receive Telegram updates. ALWAYS returns 200 — Telegram retries on 4xx/5xx."""
    expected = settings.TELEGRAM_WEBHOOK_SECRET
    # Without a secret anyone could post fake updates, so refuse them all.
    if not expected or not hmac.compare_digest(x_telegram_bot_api_secret_token or "", expected):
        # Return 200 even on auth failure to prevent Telegram retry storms
        return {"ok": False, "error": "invalid secret"}

    try:
        update = await request.json()
        await _handle_update(update)
    except Exception as exc:
        # Never let exceptions propagate — Telegram would retry indefinitely
        from loguru import logger
        logger.warning(f"Telegram webhook handler error: {exc}")

    return {"ok": True}
