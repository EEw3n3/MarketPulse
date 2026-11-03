"""Check the Paddle settings: which are set (values are never printed), that
the three price ids are the right prices, and where Paddle sends webhooks.

Usage (inside the app container):
    python scripts/paddle_check.py
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings  # noqa: E402
from app.services import billing  # noqa: E402

WANT_EVENTS = {"subscription.created", "subscription.activated", "subscription.updated",
               "subscription.canceled", "subscription.past_due", "subscription.paused",
               "subscription.resumed"}


def show(name: str, value) -> None:
    print(f"  {name:24} {'set' if value else 'MISSING'}")


async def main() -> int:
    bad = 0
    print(f"environment: {settings.PADDLE_ENV}")
    for name in ("PADDLE_CLIENT_TOKEN", "PADDLE_API_KEY", "PADDLE_WEBHOOK_SECRET",
                 "PADDLE_PRICE_MONTH", "PADDLE_PRICE_HALF", "PADDLE_PRICE_YEAR"):
        show(name, getattr(settings, name))
    token = settings.PADDLE_CLIENT_TOKEN or ""
    if token and not token.startswith("test_" if billing.sandbox() else "live_"):
        print(f"  ! the client token does not look like a {settings.PADDLE_ENV} token "
              f"({'test_' if billing.sandbox() else 'live_'}...)")
        bad += 1
    if not settings.PADDLE_API_KEY:
        print("cannot ask Paddle without the API key")
        return 1

    print("prices:")
    for p in billing.PLANS:
        pid = billing.price_id(p)
        if not pid:
            print(f"  {p.term:6} MISSING")
            bad += 1
            continue
        try:
            price = await billing.get_price(pid)
        except billing.PaddleError as e:
            print(f"  {p.term:6} {pid}: {e}")
            bad += 1
            continue
        unit = price.get("unit_price") or {}
        cycle = price.get("billing_cycle") or {}
        amount = int(unit.get("amount") or 0) / 100
        months = int(cycle.get("frequency") or 0) * (12 if cycle.get("interval") == "year" else 1)
        ok = (unit.get("currency_code") == "EUR" and abs(amount - p.amount) < 0.005 and months == p.months
              and price.get("status") == "active")
        # The site says "prices include VAT": the buyer pays exactly the price shown.
        vat_in = price.get("tax_mode") == "internal"
        bad += not ok or not vat_in
        print(f"  {p.term:6} {pid}: {amount:.2f} {unit.get('currency_code')} every {cycle.get('frequency')} "
              f"{cycle.get('interval')} ({price.get('status')}) {'ok' if ok else '<- want %.2f EUR every %d months' % (p.amount, p.months)}")
        if not vat_in:
            print(f"         tax: {price.get('tax_mode')} <- want 'Including tax' (internal) on this price")

    print("webhook destinations:")
    try:
        async with billing.httpx.AsyncClient(base_url=billing._api_base(), timeout=20) as c:
            r = await c.get("/notification-settings", headers={"Authorization": f"Bearer {settings.PADDLE_API_KEY}"})
        dests = (r.json().get("data") or []) if r.status_code < 400 else []
        if r.status_code >= 400:
            print(f"  could not read them (Paddle {r.status_code}); check in the dashboard")
        for d in dests:
            events = {e.get("name") for e in d.get("subscribed_events") or []}
            missing = WANT_EVENTS - events
            bad += bool(missing) and str(d.get("destination", "")).endswith("/api/billing/webhook")
            print(f"  {d.get('destination')} active={d.get('active')} "
                  f"{'all needed events' if not missing else 'missing: ' + ', '.join(sorted(missing))}")
        if r.status_code < 400 and not any(str(d.get("destination", "")).endswith("/api/billing/webhook") for d in dests):
            print("  ! no destination ends with /api/billing/webhook")
            bad += 1
    except Exception as e:  # informational only
        print(f"  could not read them: {e}")
    print("OK" if not bad else f"{bad} problem(s) above")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
