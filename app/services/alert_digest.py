"""Daily price-alert digest: one e-mail and one Telegram message per user.

Runs once a day after all shops are scanned (server timer, 13:00 Riga), so it
covers every shop, including the ones the PC worker uploads (Notino, 220.lv).

For every favorite with the bell on, today's price is compared with the price
in the last message about that bottle (Favorite.last_alert_price; before the
first message, the price when it was saved). The user hears about:
  * a drop of at least the bottle's threshold (or the user's general one);
  * a bottle back in stock.
A price that only rises and falls back (shops that flip between two prices)
sends nothing: the reference moves up to a higher price only once that price
has held for the whole previous week (_held_floor), and a drop is measured
from there.

Usage (inside the app container):
  python -m app.services.alert_digest --dry-run      # who would get what; sends and saves nothing
  python -m app.services.alert_digest --baseline     # remember today's prices, send nothing
  python -m app.services.alert_digest                # the real run
  python -m app.services.alert_digest --test-user 2  # a sample digest to one user; saves nothing
  python -m app.services.alert_digest --user 2       # the real run for one user only
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import os
import pathlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from jinja2 import Environment, FileSystemLoader, select_autoescape
from loguru import logger
from sqlalchemy.future import select

from app.core.config import settings
from app.domain.models import Favorite, PriceHistory, Product, User, UserPreferences
from app.services.email_sender import email_configured, send_email
from app.services.telegram_bot import bot, escape_md

# A product the scanners have not seen for this long has no trustworthy price.
STALE_AFTER = timedelta(days=3)
# A bigger "drop" is nearly always a parser mix-up (another volume's price);
# it is reported in the log and not sent.
MAX_PLAUSIBLE_DROP_PCT = 60.0
# At most one message about a bottle a day, even when the job is run twice.
MIN_GAP = timedelta(hours=20)
# Resend free plan: 100 e-mails a UTC day. Keep a margin for other mail.
MAX_EMAILS = int(os.getenv("DIGEST_MAX_EMAILS") or "90")
# A higher price becomes the reference once it held for this long. The
# window ends before today's scans (night ones end by ~07:00 Riga, the day
# scan by ~11:00; the digest runs at 13:00).
HOLD_WINDOW = timedelta(days=7)
TODAY_SCANS = timedelta(hours=16)
# Telegram messages are limited to 4096 characters.
MAX_TG_ITEMS = 15

_TEMPLATE_DIR = pathlib.Path(__file__).parent.parent / "templates"
_jinja = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=select_autoescape(["html"]))

_STORE_NAMES = {
    "douglas.lv": "Douglas",
    "notino.lv": "Notino",
    "makeup.lv": "Makeup.lv",
    "220.lv": "220.lv",
    "1a.lv": "1a.lv",
}


def unsubscribe_token(user_id: int) -> str:
    """Signed token for the e-mail's one-click unsubscribe link."""
    key = (settings.JWT_SECRET or "").encode()
    return hmac.new(key, f"unsubscribe-email:{user_id}".encode(), hashlib.sha256).hexdigest()[:32]


def unsubscribe_url(user_id: int) -> str:
    base = (settings.PUBLIC_BASE_URL or "").rstrip("/")
    return f"{base}/api/notifications/unsubscribe?u={user_id}&t={unsubscribe_token(user_id)}"


@dataclass
class Item:
    fav: Favorite
    product: Product
    kind: str  # "drop" | "back" | "test"
    new_price: Decimal
    ref_price: Decimal | None

    @property
    def pct(self) -> float:
        if not self.ref_price or self.ref_price <= 0:
            return 0.0
        return float((self.new_price - self.ref_price) / self.ref_price * 100)

    @property
    def store(self) -> str:
        return _STORE_NAMES.get(self.product.search_term, self.product.search_term)

    @property
    def name(self) -> str:
        p = self.product
        brand = (p.brand or "").strip()
        title = p.title.strip()
        full = title if not brand or title.lower().startswith(brand.lower()) else f"{brand} {title}"
        if p.volume and p.volume.lower() not in full.lower():
            full = f"{full} {p.volume}"
        return full


@dataclass
class UserDigest:
    user: User
    prefs: UserPreferences
    items: list[Item] = field(default_factory=list)


async def _held_floor(db, product_id: int, now: datetime) -> Decimal | None:
    """Lowest price the product had at any moment of the previous week (before
    today's scans), from real history only. None when there is no history."""
    end = now - TODAY_SCANS
    start = end - HOLD_WINDOW
    real = (PriceHistory.product_id == product_id, PriceHistory.change_type != "synthetic", PriceHistory.price > 0)
    before = (await db.execute(
        select(PriceHistory.price).where(*real, PriceHistory.parsed_at <= start)
        .order_by(PriceHistory.parsed_at.desc()).limit(1)
    )).scalar_one_or_none()
    inside = (await db.execute(
        select(PriceHistory.price).where(*real, PriceHistory.parsed_at > start, PriceHistory.parsed_at <= end)
    )).scalars().all()
    prices = [p for p in [before, *inside] if p is not None]
    return min(prices) if prices else None


def _evaluate(fav: Favorite, product: Product, prefs: UserPreferences, now: datetime,
              floor: Decimal | None = None) -> tuple[Item | None, str]:
    """Return (item to send or None, note for the log). Records a lost stock
    on fav (so its return is news); the caller commits or not."""
    price = product.last_price if product.last_price and product.last_price > 0 else None
    avail = bool(product.is_available)
    if product.last_seen is None or now - product.last_seen > STALE_AFTER:
        return None, "stale"
    if fav.last_alert_at and now - fav.last_alert_at < MIN_GAP:
        return None, "told recently"

    ref = fav.last_alert_price if fav.last_alert_price is not None else fav.price_when_added
    raised = False
    # A message inside the window already set the reference: the user knows
    # that price, so an older, higher one does not count.
    told_lately = fav.last_alert_at is not None and fav.last_alert_at > now - TODAY_SCANS - HOLD_WINDOW
    if floor is not None and not told_lately and (ref is None or floor > ref):
        ref, raised = floor, True  # a higher price held all week
    was_in_stock = fav.last_alert_in_stock

    if fav.alert_threshold_percent is not None:
        threshold = float(fav.alert_threshold_percent)
    else:
        threshold = float(prefs.notification_threshold_percent or Decimal("5.0"))

    if price is not None and avail and was_in_stock is False:
        return Item(fav, product, "back", price, ref), "back in stock"

    if price is not None and avail and ref and ref > 0 and price < ref:
        drop = float((ref - price) / ref * 100)
        if drop > MAX_PLAUSIBLE_DROP_PCT:
            return None, f"suspicious drop -{drop:.0f}% ({ref} -> {price}), not sent"
        if drop >= threshold:
            return Item(fav, product, "drop", price, ref), f"drop -{drop:.1f}%"
        note = f"small drop -{drop:.1f}% < {threshold:g}%"
    elif price is not None and ref and price > ref:
        note = f"above reference {ref}"
    else:
        note = "no change"
    if raised:
        note += " (reference = price held all week)"

    if was_in_stock is None or was_in_stock != avail:
        if not (avail and was_in_stock is False):
            fav.last_alert_in_stock = avail
    return None, note


def _channels(user: User, prefs: UserPreferences) -> list[str]:
    out = []
    chosen = prefs.notification_channels or []
    if "email" in chosen and user.email and email_configured():
        out.append("email")
    if "telegram" in chosen and prefs.telegram_chat_id and settings.TELEGRAM_BOT_TOKEN:
        out.append("telegram")
    return out


def _mask(email: str | None) -> str:
    if not email or "@" not in email:
        return "-"
    name, dom = email.split("@", 1)
    return f"{name[:2]}***@{dom}"


def _product_url(p: Product) -> str:
    return f"{(settings.PUBLIC_BASE_URL or '').rstrip('/')}/product/{p.id}"


def render_email(d: UserDigest, test: bool = False) -> tuple[str, str, str]:
    """(subject, html, text) for one user's digest."""
    items = d.items
    drops = [i for i in items if i.kind in ("drop", "test")]
    if test:
        subject = "Test: your MarketPulse price alerts"
    elif len(items) == 1:
        i = items[0]
        subject = (
            f"{i.name} is back in stock at {i.store}" if i.kind == "back"
            else f"{i.name}: -{abs(i.pct):.0f}% at {i.store}"
        )
    else:
        subject = f"{len(items)} of your saved bottles got cheaper or came back"
    base = (settings.PUBLIC_BASE_URL or "").rstrip("/")
    ctx = dict(
        items=[
            dict(
                name=i.name,
                store=i.store,
                kind=i.kind,
                new_price=float(i.new_price),
                ref_price=float(i.ref_price) if i.ref_price else None,
                pct=i.pct,
                image_url=i.product.image_url,
                product_url=_product_url(i.product),
            )
            for i in items
        ],
        test=test,
        drops=len(drops),
        favorites_url=f"{base}/favorites",
        profile_url=f"{base}/profile",
        unsubscribe_url=unsubscribe_url(d.user.id),
    )
    html = _jinja.get_template("alert_digest.html").render(**ctx)
    lines = ["Test message: this is how your alerts will look.", ""] if test else []
    for i in items:
        if i.kind == "back":
            lines.append(f"Back in stock: {i.name}, {i.store}, EUR {i.new_price:.2f}")
        else:
            was = f" (was {i.ref_price:.2f}, {i.pct:+.1f}%)" if i.ref_price and i.ref_price != i.new_price else ""
            lines.append(f"{i.name}, {i.store}: EUR {i.new_price:.2f}{was}")
        lines.append(f"  {_product_url(i.product)}")
    lines += ["", f"Alert settings: {base}/profile", f"Stop these e-mails: {unsubscribe_url(d.user.id)}"]
    return subject, html, "\n".join(lines)


def render_telegram(d: UserDigest, test: bool = False) -> str:
    out = ["🧪 *Test message*: this is how your alerts will look\\." if test else "🔔 *MarketPulse price alerts*"]
    for i in d.items[:MAX_TG_ITEMS]:
        name = escape_md(i.name)
        store = escape_md(i.store)
        price = escape_md(f"€{i.new_price:.2f}")
        link = escape_md(_product_url(i.product))
        if i.kind == "back":
            out.append(f"📦 *{name}* is back in stock\n{price} · {store} · [open]({link})")
        else:
            was = ""
            if i.ref_price and i.ref_price != i.new_price:
                was = f" ~{escape_md(f'€{i.ref_price:.2f}')}~ *{escape_md(f'{i.pct:+.1f}%')}*"
            out.append(f"📉 *{name}*\n{price}{was} · {store} · [open]({link})")
    rest = len(d.items) - MAX_TG_ITEMS
    if rest > 0:
        out.append(escape_md(f"…and {rest} more on the Favorites page."))
    return "\n\n".join(out)


async def _deliver(d: UserDigest, channels: list[str], test: bool, budget: dict) -> list[str]:
    done = []
    if "email" in channels:
        if budget["emails"] >= MAX_EMAILS:
            logger.warning(f"[DIGEST] e-mail limit {MAX_EMAILS} reached; user={d.user.id} gets no e-mail today")
        else:
            subject, html, text = render_email(d, test)
            u = unsubscribe_url(d.user.id)
            headers = {"List-Unsubscribe": f"<{u}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}
            budget["emails"] += 1
            if await send_email(to_email=d.user.email, subject=subject, html_body=html, text_body=text, headers=headers):
                done.append("email")
    if "telegram" in channels:
        if await bot.send_message(d.prefs.telegram_chat_id, render_telegram(d, test)):
            done.append("telegram")
    return done


async def run(*, dry_run: bool = False, baseline: bool = False, only_user: int | None = None,
              test_user: int | None = None) -> dict:
    from app.core.database import async_session_maker

    now = datetime.utcnow()
    stats = {"users": 0, "items": 0, "sent_users": 0, "emails": 0, "telegrams": 0, "failed": 0, "skipped_no_channel": 0}
    async with async_session_maker() as db:
        stmt = (
            select(Favorite, Product, User, UserPreferences)
            .join(Product, Product.id == Favorite.product_id)
            .join(User, User.id == Favorite.user_id)
            .join(UserPreferences, UserPreferences.user_id == User.id)
            .where(Favorite.alert_enabled.is_(True), User.is_active.is_(True))
            .order_by(User.id, Favorite.id)
        )
        uid = test_user or only_user
        if uid:
            stmt = stmt.where(User.id == uid)
        rows = (await db.execute(stmt)).all()

        if baseline:
            for fav, product, _u, _p in rows:
                price = product.last_price if product.last_price and product.last_price > 0 else fav.price_when_added
                fav.last_alert_price = price
                fav.last_alert_in_stock = bool(product.is_available)
            if not dry_run:
                await db.commit()
            logger.info(f"[DIGEST] baseline: {len(rows)} favorites remember today's price{' (dry run, not saved)' if dry_run else ''}")
            return {"baseline": len(rows)}

        digests: dict[int, UserDigest] = {}
        for fav, product, user, prefs in rows:
            d = digests.setdefault(user.id, UserDigest(user, prefs))
            if test_user:
                if len(d.items) < 3 and product.last_price and product.last_price > 0:
                    ref = fav.last_alert_price or fav.price_when_added or product.last_price
                    d.items.append(Item(fav, product, "test", product.last_price, ref))
                continue
            floor = await _held_floor(db, product.id, now)
            item, note = _evaluate(fav, product, prefs, now, floor)
            if dry_run or item is not None or note.startswith("suspicious"):
                logger.info(f"[DIGEST] user={user.id} fav={fav.id} product={product.id} {product.search_term}: {note}")
            if item:
                d.items.append(item)

        budget = {"emails": 0}
        for d in digests.values():
            if not d.items:
                continue
            stats["users"] += 1
            stats["items"] += len(d.items)
            channels = _channels(d.user, d.prefs)
            names = "; ".join(f"{i.name} {i.store} {i.kind} {i.pct:+.1f}%" for i in d.items)
            if not channels:
                stats["skipped_no_channel"] += 1
                logger.info(f"[DIGEST] user={d.user.id} ({_mask(d.user.email)}) has no working channel; kept for later: {names}")
                continue
            if dry_run:
                logger.info(f"[DIGEST] DRY RUN would send {channels} to user={d.user.id} ({_mask(d.user.email)}): {names}")
                continue
            done = await _deliver(d, channels, bool(test_user), budget)
            stats["emails"] += done.count("email")
            stats["telegrams"] += done.count("telegram")
            if done:
                stats["sent_users"] += 1
                logger.info(f"[DIGEST] sent {done} to user={d.user.id}: {names}")
                if not test_user:
                    for i in d.items:
                        i.fav.last_alert_price = i.new_price
                        i.fav.last_alert_in_stock = True
                        i.fav.last_alert_at = now
            else:
                stats["failed"] += 1
                logger.warning(f"[DIGEST] delivery failed for user={d.user.id}; will retry tomorrow")

        if dry_run or test_user:
            await db.rollback()
        else:
            await db.commit()
    logger.info(f"[DIGEST] {'DRY RUN ' if dry_run else ''}done: {stats}")
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Daily price-alert digest")
    ap.add_argument("--dry-run", action="store_true", help="show who would get what; send and save nothing")
    ap.add_argument("--baseline", action="store_true", help="remember today's prices for every favorite, send nothing")
    ap.add_argument("--user", type=int, help="real run for this user id only")
    ap.add_argument("--test-user", type=int, help="send a sample digest to this user id; saves nothing")
    a = ap.parse_args()
    stats = asyncio.run(run(dry_run=a.dry_run, baseline=a.baseline, only_user=a.user, test_user=a.test_user))
    print(stats)


if __name__ == "__main__":
    main()
