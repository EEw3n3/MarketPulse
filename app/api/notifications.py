"""One-click unsubscribe from alert e-mails (link and List-Unsubscribe header).

GET shows a page with a button, so mail scanners that open links do not
unsubscribe anyone; POST (the button, or a mail client's one-click request
per RFC 8058) removes "email" from the user's alert channels.
"""
import hmac
from html import escape

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.deps import get_db
from app.core.config import settings
from app.domain.models import UserPreferences
from app.services.alert_digest import unsubscribe_token

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _page(title: str, body: str) -> HTMLResponse:
    base = escape((settings.PUBLIC_BASE_URL or "").rstrip("/"))
    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(title)} · MarketPulse</title></head>
<body style="margin:0;background:#f4f4f2;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:#1a1a1a">
<div style="max-width:440px;margin:48px auto;padding:24px;background:#fff;border:1px solid #e4e4e0;border-radius:12px">
<h1 style="font-size:20px;margin:0 0 12px">{escape(title)}</h1>{body}
<p style="margin-top:20px;font-size:13px"><a href="{base}/profile" style="color:#15803d">Alert settings</a></p>
</div></body></html>"""
    return HTMLResponse(html)


def _valid(u: int, t: str) -> bool:
    return hmac.compare_digest(unsubscribe_token(u), t or "")


@router.get("/unsubscribe", response_class=HTMLResponse)
async def unsubscribe_page(u: int = Query(...), t: str = Query("")):
    if not _valid(u, t):
        return _page("Link not valid", "<p>Change your alert e-mails in the profile instead.</p>")
    form = (
        f'<p>Stop price-alert e-mails for this account? Telegram alerts, if any, stay on.</p>'
        f'<form method="post" action="?u={u}&t={escape(t)}">'
        f'<button type="submit" style="background:#15803d;color:#fff;border:0;border-radius:8px;'
        f'padding:10px 18px;font-weight:700;font-size:14px;cursor:pointer">Stop e-mails</button></form>'
    )
    return _page("Stop alert e-mails", form)


@router.post("/unsubscribe", response_class=HTMLResponse)
async def unsubscribe(u: int = Query(...), t: str = Query(""), db: AsyncSession = Depends(get_db)):
    if not _valid(u, t):
        return _page("Link not valid", "<p>Change your alert e-mails in the profile instead.</p>")
    prefs = (await db.execute(select(UserPreferences).where(UserPreferences.user_id == u))).scalar_one_or_none()
    if prefs and "email" in (prefs.notification_channels or []):
        prefs.notification_channels = [c for c in prefs.notification_channels if c != "email"]
        await db.commit()
    return _page("E-mails stopped", "<p>You will get no more price-alert e-mails. You can turn them back on in the profile.</p>")
