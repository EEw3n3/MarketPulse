"""E-mail delivery: Resend HTTP API first, SMTP as the fallback.

Resend is preferred on servers: it needs only HTTPS out, and the free plan
(100 e-mails a day, 3,000 a month) is enough for one digest a day per user.
"""
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from loguru import logger

from app.core.config import settings


def email_configured() -> bool:
    return bool(settings.RESEND_API_KEY or (settings.SMTP_USER and settings.SMTP_PASSWORD))


async def _send_via_resend(
    *, to_email: str, subject: str, html_body: str, text_body: str | None, headers: dict | None
) -> bool:
    import httpx

    payload: dict = {
        "from": settings.RESEND_FROM,
        "to": [to_email],
        "subject": subject,
        "html": html_body,
    }
    if text_body:
        payload["text"] = text_body
    if headers:
        payload["headers"] = headers
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                "https://api.resend.com/emails",
                json=payload,
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            )
        if r.status_code // 100 == 2:
            logger.info(f"[EMAIL] Resend -> user mail: {r.json().get('id', 'ok')}")
            return True
        logger.warning(f"[EMAIL] Resend HTTP {r.status_code}: {r.text[:200]}")
        return False
    except Exception as exc:
        logger.warning(f"[EMAIL] Resend exception: {exc}")
        return False


async def _send_via_smtp(
    *, to_email: str, subject: str, html_body: str, text_body: str | None, headers: dict | None
) -> bool:
    import aiosmtplib

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email
    for k, v in (headers or {}).items():
        msg[k] = v
    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            use_tls=settings.SMTP_PORT == 465,
            start_tls=settings.SMTP_PORT != 465,
            timeout=15,
        )
        logger.info("[EMAIL] SMTP -> user mail sent")
        return True
    except Exception as exc:
        logger.warning(f"[EMAIL] SMTP failed: {exc}")
        return False


async def send_email(
    *,
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
    headers: dict | None = None,
) -> bool:
    """Send one e-mail. Returns True when the provider accepted it."""
    if not email_configured():
        logger.debug("Neither RESEND_API_KEY nor SMTP_USER/PASSWORD set; e-mail skipped")
        return False
    kw = dict(to_email=to_email, subject=subject, html_body=html_body, text_body=text_body, headers=headers)
    if settings.RESEND_API_KEY:
        return await _send_via_resend(**kw)
    return await _send_via_smtp(**kw)
