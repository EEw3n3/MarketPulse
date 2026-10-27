"""Notification dispatcher — sends price alerts via Telegram and/or Email.

CRITICAL: Always call dispatch_price_alert() AFTER session.commit().
If the transport fails before commit, the transaction rolls back and PriceHistory is lost.
"""
import asyncio
from dataclasses import dataclass
from decimal import Decimal

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.domain.models import Favorite, Product, PriceHistory, User, UserPreferences
from app.services.telegram_bot import bot, escape_md
from app.services.email_sender import send_price_alert_email
from app.core.config import settings


@dataclass
class _AlertPayload:
    product: Product
    history: PriceHistory
    user: User
    prefs: UserPreferences
    percent_change: float


async def _send_telegram(payload: _AlertPayload) -> None:
    chat_id = payload.prefs.telegram_chat_id
    if not chat_id:
        return

    p = payload.product
    h = payload.history
    pct = abs(payload.percent_change)

    icon = {"price_down": "📉", "price_up": "📈", "back_in_stock": "📦"}.get(h.change_type, "🔔")
    brand_part = escape_md(p.brand or "")
    title_part = escape_md(p.title)
    store_part = escape_md(p.search_term.capitalize())
    new_price = escape_md(f"{float(h.price):.2f}")
    old_price_str = ""
    if p.old_price:
        old_price_str = f" ~€{escape_md(f'{float(p.old_price):.2f}')}~"

    if h.change_type == "price_down":
        change_str = escape_md(f"−{pct:.1f}%")
        headline = f"{icon} *{brand_part} {title_part}* dropped *{change_str}*"
    elif h.change_type == "back_in_stock":
        headline = f"{icon} *{brand_part} {title_part}* is back in stock"
    else:
        change_str = escape_md(f"+{pct:.1f}%")
        headline = f"{icon} *{brand_part} {title_part}* increased *{change_str}*"

    base_url = (settings.PUBLIC_BASE_URL or "").rstrip("/")
    product_url = escape_md(f"{base_url}/product/{p.id}")

    text = (
        f"{headline}\n"
        f"€{new_price}{old_price_str} · {store_part}\n"
        f"[View on MarketPulse]({product_url})"
    )

    await bot.send_message(chat_id, text)
    logger.info(f"[DISPATCH] Telegram sent to user={payload.user.id} product={p.id}")


async def _send_email(payload: _AlertPayload) -> None:
    if not payload.user.email:
        return
    base_url = (settings.PUBLIC_BASE_URL or "").rstrip("/")
    p = payload.product
    h = payload.history

    sent = await send_price_alert_email(
        to_email=payload.user.email,
        user_id=payload.user.id,
        product_id=p.id,
        title=p.title,
        brand=p.brand,
        store_name=p.search_term.capitalize(),
        image_url=p.image_url,
        new_price=float(h.price),
        old_price=float(p.old_price) if p.old_price else None,
        change_type=h.change_type,
        change_percent=payload.percent_change,
        base_url=base_url,
    )
    if sent:
        logger.info(f"[DISPATCH] Email sent to user={payload.user.id} product={p.id}")
    else:
        logger.warning(
            f"[DISPATCH] Email NOT delivered to user={payload.user.id} product={p.id}"
            " — check SMTP / RESEND config and provider logs"
        )


class NotificationDispatcher:
    """Orchestrates alert delivery for a price-change event."""

    async def dispatch_price_alert(
        self,
        db: AsyncSession,
        product: Product,
        history: PriceHistory,
        percent_change: float,
    ) -> None:
        """Send alerts to all users who track this product with alert_enabled=True.

        Must be called after session.commit() — see module docstring.
        """
        if history.change_type not in ("price_down", "price_up", "back_in_stock"):
            return

        stmt = (
            select(Favorite, User, UserPreferences)
            .join(User, User.id == Favorite.user_id)
            .join(UserPreferences, UserPreferences.user_id == User.id)
            .where(
                Favorite.product_id == product.id,
                Favorite.alert_enabled.is_(True),
                User.is_active.is_(True),
            )
        )
        rows = (await db.execute(stmt)).all()

        tasks: list = []
        for fav, user, prefs in rows:
            # back_in_stock bypasses the threshold — always notify
            if history.change_type != "back_in_stock":
                # A bottle's own threshold wins over the user's general one.
                if fav.alert_threshold_percent is not None:
                    threshold = float(fav.alert_threshold_percent)
                else:
                    threshold = float(prefs.notification_threshold_percent or Decimal("5.0"))
                if abs(percent_change) < threshold:
                    continue

            payload = _AlertPayload(
                product=product,
                history=history,
                user=user,
                prefs=prefs,
                percent_change=percent_change,
            )

            for channel in (prefs.notification_channels or []):
                if channel == "telegram" and prefs.telegram_chat_id:
                    tasks.append(_send_telegram(payload))
                elif channel == "email" and user.email:
                    tasks.append(_send_email(payload))

        if not tasks:
            return

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                logger.warning(f"[DISPATCH] Alert task failed: {r}")


dispatcher = NotificationDispatcher()
