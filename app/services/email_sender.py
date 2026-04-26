"""Async email sender using aiosmtplib + Jinja2 templates."""
import pathlib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Environment, FileSystemLoader, select_autoescape
from loguru import logger

from app.core.config import settings

_TEMPLATE_DIR = pathlib.Path(__file__).parent.parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)

# Per-user email rate cap: product_id → last_sent timestamp
# Prevents bursting > 1 email per favorite per 6 hours.
_last_sent: dict[str, float] = {}  # key: f"{user_id}:{product_id}"
_EMAIL_COOLDOWN_S = 6 * 3600


def _is_rate_limited(user_id: int, product_id: int) -> bool:
    import time
    key = f"{user_id}:{product_id}"
    last = _last_sent.get(key, 0.0)
    if time.time() - last < _EMAIL_COOLDOWN_S:
        return True
    _last_sent[key] = time.time()
    return False


async def send_price_alert_email(
    *,
    to_email: str,
    user_id: int,
    product_id: int,
    title: str,
    brand: str | None,
    store_name: str,
    image_url: str | None,
    new_price: float,
    old_price: float | None,
    change_type: str,
    change_percent: float,
    base_url: str,
) -> bool:
    """Render and send a price-alert email. Returns True on success."""
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.debug("SMTP not configured — skipping email")
        return False

    if _is_rate_limited(user_id, product_id):
        logger.debug(f"Email rate-limited for user={user_id} product={product_id}")
        return False

    product_url = f"{base_url}/product/{product_id}"
    settings_url = f"{base_url}/settings"

    template = _jinja_env.get_template("price_alert.html")
    html_body = template.render(
        title=title,
        brand=brand,
        store_name=store_name,
        image_url=image_url,
        new_price=new_price,
        old_price=old_price,
        change_type=change_type,
        change_percent=change_percent,
        product_url=product_url,
        settings_url=settings_url,
    )

    subject_map = {
        "price_down": f"📉 Price drop: {title}",
        "price_up": f"📈 Price increase: {title}",
        "back_in_stock": f"📦 Back in stock: {title}",
    }
    subject = subject_map.get(change_type, f"Price alert: {title}")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    import aiosmtplib
    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
        )
        logger.info(f"[EMAIL] Sent price alert to {to_email} for product {product_id}")
        return True
    except Exception as exc:
        logger.warning(f"[EMAIL] Failed to send to {to_email}: {exc}")
        return False
