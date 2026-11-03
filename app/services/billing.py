"""Card payments for Pro through Paddle (paddle.com).

Paddle is the reseller and Merchant of Record: it shows the checkout, takes
the card, charges VAT, sends receipts and handles refunds. MarketPulse only
listens: every change of a subscription comes as a signed webhook
(POST /api/billing/webhook), and apply_event() turns it into Pro on the user:

  * active / trialing: Pro until the end of the paid period + GRACE (the
    renewal webhook comes within minutes of the period end);
  * past_due (the renewal payment failed, Paddle retries): Pro for
    PAST_DUE_GRACE from the start of the unpaid period, then off unless a retry
    succeeds (the next webhook says active again);
  * paused / canceled: paid Pro ends at that moment.

A cancellation the user asks for (in Paddle's customer portal) only schedules
the end: Pro stays until the paid period is over, then "canceled" arrives.

PADDLE_ENV "sandbox" takes test cards, so there only admins (and the emails in
PADDLE_SANDBOX_EMAILS) get Pro from a webhook: a sandbox checkout opened on the
live site by someone else gives nothing.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domain.models import PaddleEvent, Subscription, User
from app.services import plans

GRACE = timedelta(days=1)
PAST_DUE_GRACE = timedelta(days=3)
SIGNATURE_TOLERANCE = 300          # seconds between Paddle signing and us reading
PRO_STATUSES = {"active", "trialing"}


@dataclass(frozen=True)
class Plan:
    term: str          # month | half | year
    months: int
    amount: float      # EUR, what the site shows; Paddle's checkout shows the final price
    setting: str       # the Settings attribute that holds the Paddle price id


PLANS = (
    Plan("month", 1, 3.99, "PADDLE_PRICE_MONTH"),
    Plan("half", 6, 19.99, "PADDLE_PRICE_HALF"),
    Plan("year", 12, 34.99, "PADDLE_PRICE_YEAR"),
)


def price_id(plan: Plan) -> Optional[str]:
    return getattr(settings, plan.setting, None)


def configured() -> bool:
    """Checkout can open: the client token and every price id are set."""
    return bool(settings.PADDLE_CLIENT_TOKEN and all(price_id(p) for p in PLANS))


def sandbox() -> bool:
    return settings.PADDLE_ENV != "production"


def _sandbox_emails() -> set[str]:
    return {e.strip().lower() for e in settings.PADDLE_SANDBOX_EMAILS.split(",") if e.strip()}


def checkout_open_to(user: User) -> bool:
    """Who sees the checkout: everyone in production; in the sandbox only
    admins and the test emails."""
    if not configured():
        return False
    return not sandbox() or user.is_admin or user.email.lower() in _sandbox_emails()


def term_of(price: Optional[str], cycle: Optional[dict] = None) -> Optional[str]:
    for p in PLANS:
        if price and price == price_id(p):
            return p.term
    if cycle:
        months = int(cycle.get("frequency") or 0) * (12 if cycle.get("interval") == "year" else 1)
        if cycle.get("interval") in ("month", "year"):
            return next((p.term for p in PLANS if p.months == months), None)
    return None


# ── Webhook signature ────────────────────────────────────────────────────────

def verify_signature(raw: bytes, header: Optional[str], secret: Optional[str] = None,
                     now: Optional[float] = None) -> bool:
    """Paddle-Signature: "ts=1671552777;h1=eb4d0d..." where h1 is
    HMAC-SHA256(secret, f"{ts}:{raw body}"). Older than 5 minutes = refused
    (a replayed request)."""
    secret = secret if secret is not None else settings.PADDLE_WEBHOOK_SECRET
    if not secret or not header:
        return False
    parts: dict[str, list[str]] = {}
    for item in header.split(";"):
        k, _, v = item.strip().partition("=")
        parts.setdefault(k, []).append(v)
    ts = (parts.get("ts") or [""])[0]
    if not ts.isdigit() or abs((now or time.time()) - int(ts)) > SIGNATURE_TOLERANCE:
        return False
    expected = hmac.new(secret.encode(), f"{ts}:".encode() + raw, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, h) for h in parts.get("h1", []))


# ── Events ───────────────────────────────────────────────────────────────────

def _time(s: Optional[str]) -> Optional[datetime]:
    """Paddle's RFC 3339 time ("2026-11-04T10:00:00.123456Z") as naive UTC."""
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.astimezone(timezone.utc).replace(tzinfo=None) if d.tzinfo else d


async def _user_for(db: AsyncSession, data: dict, sub: Optional[Subscription]) -> Optional[User]:
    raw = (data.get("custom_data") or {}).get("user_id")
    try:
        uid = int(raw) if raw is not None else None
    except (TypeError, ValueError):
        uid = None
    if uid is None and sub is not None:
        uid = sub.user_id
    return await db.get(User, uid) if uid else None


async def apply_event(db: AsyncSession, event: dict) -> str:
    """Apply one webhook (already verified). Returns what was done, for the
    log; the caller commits. Each event_id is applied once."""
    event_id = str(event.get("event_id") or "")
    etype = str(event.get("event_type") or "")
    occurred = _time(event.get("occurred_at")) or datetime.utcnow()
    if not event_id:
        return "no event_id: skipped"
    if await db.get(PaddleEvent, event_id):
        return "already applied"
    row = PaddleEvent(id=event_id, event_type=etype[:64], occurred_at=occurred)
    db.add(row)
    if not etype.startswith("subscription."):
        row.result = "not a subscription event: nothing to do"
        return row.result

    data = event.get("data") or {}
    sid = str(data.get("id") or "")
    row.subscription_id = sid[:64] or None
    if not sid:
        row.result = "no subscription id"
        return row.result
    sub = (await db.execute(select(Subscription).where(Subscription.paddle_subscription_id == sid))).scalar_one_or_none()
    user = await _user_for(db, data, sub)
    row.user_id = user.id if user else None
    if sub is not None and sub.last_event_at and occurred < sub.last_event_at:
        row.result = "older than the last applied event: skipped"
        return row.result

    status = str(data.get("status") or "")
    items = data.get("items") or []
    price = ((items[0] or {}).get("price") or {}) if items else {}
    period = data.get("current_billing_period") or {}
    period_start, period_end = _time(period.get("starts_at")), _time(period.get("ends_at"))
    scheduled = data.get("scheduled_change") or {}
    cancel_at = _time(scheduled.get("effective_at")) if scheduled.get("action") == "cancel" else None

    if sub is None:
        sub = Subscription(paddle_subscription_id=sid[:64], status=status[:16] or "unknown")
        db.add(sub)
    if user is not None:
        sub.user_id = user.id
    sub.paddle_customer_id = (data.get("customer_id") or sub.paddle_customer_id or None)
    sub.status = status[:16] or sub.status
    sub.price_id = (price.get("id") or sub.price_id or None)
    sub.term = term_of(sub.price_id, price.get("billing_cycle") or data.get("billing_cycle")) or sub.term
    sub.current_period_end = period_end or sub.current_period_end
    sub.cancel_at = cancel_at
    sub.last_event_at = occurred
    sub.updated_at = datetime.utcnow()

    if user is None:
        row.result = f"{status}: no MarketPulse account in custom_data (subscription kept)"
        return row.result
    if sandbox() and not (user.is_admin or user.email.lower() in _sandbox_emails()):
        row.result = f"{status}: sandbox payment of a non-test account, Pro not given"
        logger.warning(f"paddle: sandbox subscription {sid} for user {user.id} ignored")
        return row.result

    note = f"Paddle {sid}"
    if status in PRO_STATUSES and period_end:
        change = plans.paid_until(db, user, period_end + GRACE, note)
        row.result = f"{status}: Pro until {period_end + GRACE:%Y-%m-%d %H:%M} UTC" + ("" if change else " (no change)")
    elif status == "past_due":
        until = (period_start or occurred) + PAST_DUE_GRACE
        if until > datetime.utcnow():
            plans.paid_until(db, user, until, note + " past due")
        else:
            plans.payment_ended(db, user, datetime.utcnow(), note + " past due")
        row.result = f"past_due: Pro until {until:%Y-%m-%d %H:%M} UTC while Paddle retries"
    elif status in ("paused", "canceled"):
        at = _time(data.get("canceled_at") if status == "canceled" else data.get("paused_at")) or occurred
        plans.payment_ended(db, user, min(at, datetime.utcnow()), note + f" {status}")
        row.result = f"{status}: paid Pro ended"
    else:
        row.result = f"{status}: nothing to do"
    if cancel_at:
        row.result += f"; ends {cancel_at:%Y-%m-%d}"
    return row.result[:255]


# ── Paddle API ───────────────────────────────────────────────────────────────

class PaddleError(Exception):
    pass


def _api_base() -> str:
    return "https://sandbox-api.paddle.com" if sandbox() else "https://api.paddle.com"


async def _api(method: str, path: str, json: Optional[dict] = None) -> dict:
    if not settings.PADDLE_API_KEY:
        raise PaddleError("PADDLE_API_KEY is not set")
    async with httpx.AsyncClient(base_url=_api_base(), timeout=20) as client:
        r = await client.request(method, path, json=json,
                                 headers={"Authorization": f"Bearer {settings.PADDLE_API_KEY}"})
    if r.status_code >= 400:
        try:
            detail = r.json().get("error", {}).get("detail") or r.text
        except ValueError:
            detail = r.text
        raise PaddleError(f"Paddle {r.status_code}: {str(detail)[:200]}")
    return r.json().get("data") or {}


async def portal_url(sub: Subscription) -> str:
    """A one-time link to Paddle's customer portal for this subscription:
    change the card, see receipts, cancel."""
    if not sub.paddle_customer_id:
        raise PaddleError("the subscription has no Paddle customer yet")
    data = await _api("POST", f"/customers/{sub.paddle_customer_id}/portal-sessions",
                      {"subscription_ids": [sub.paddle_subscription_id]})
    urls = data.get("urls") or {}
    url = (urls.get("general") or {}).get("overview")
    if not url:
        raise PaddleError("Paddle sent no portal link")
    return url


async def cancel_now(sub: Subscription) -> None:
    """Stop the subscription at once (the account is being deleted)."""
    await _api("POST", f"/subscriptions/{sub.paddle_subscription_id}/cancel", {"effective_from": "immediately"})


async def get_price(pid: str) -> dict:
    return await _api("GET", f"/prices/{pid}")


async def live_subscription(db: AsyncSession, user_id: int) -> Optional[Subscription]:
    """The user's subscription that can still charge them (not canceled)."""
    return (await db.execute(
        select(Subscription).where(Subscription.user_id == user_id, Subscription.status != "canceled")
        .order_by(Subscription.updated_at.desc()).limit(1)
    )).scalar_one_or_none()
