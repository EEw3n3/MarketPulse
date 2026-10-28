import os

from dotenv import load_dotenv

# Load variables from .env file into memory
load_dotenv()

class Settings:
    PROJECT_NAME: str = "MarketPulse"
    VERSION: str = "1.2.0"

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///database.db")
    
    # OpenAI
    # OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    # OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini") # If env is empty, take 4o-mini

    # Gemini
    GOOGLE_API_KEY: str | None = os.getenv("GOOGLE_API_KEY")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.0-pro")
    
    # Scraping Config
    DEFAULT_TARGET_COUNT: int = 20
    MAX_CONCURRENT_SCRAPES: int = 3
    SCRAPE_INTERVAL_HOURS: int = int(os.getenv("SCRAPE_INTERVAL_HOURS", "12"))
    PRODUCTION_MAX_ITEMS: int = int(os.getenv("PRODUCTION_MAX_ITEMS", "9999"))

    # Delays between paginated page loads (seconds)
    PAGE_DELAY_MIN: float = 2.0
    PAGE_DELAY_MAX: float = 5.0

    # Cooldown when a 429 / 503 rate-limit response is received (seconds)
    RATE_LIMIT_COOLDOWN_MIN: float = 30.0
    RATE_LIMIT_COOLDOWN_MAX: float = 60.0

    # Auth (JWT)
    # No default: tokens must never be signed with a known string.
    JWT_SECRET: str = os.getenv("JWT_SECRET") or ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Admin bootstrap: email that auto-receives is_admin=True on registration.
    ADMIN_EMAIL: str | None = os.getenv("ADMIN_EMAIL")

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str | None = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_BOT_USERNAME: str = os.getenv("TELEGRAM_BOT_USERNAME", "MarketPulseBot")
    TELEGRAM_WEBHOOK_SECRET: str | None = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    # Set to "true" to use long-polling instead of webhook (dev without public URL)
    TELEGRAM_POLLING: bool = os.getenv("TELEGRAM_POLLING", "false").lower() == "true"

    # Public base URL for webhook registration (e.g. https://api.marketpulse.app)
    PUBLIC_BASE_URL: str | None = os.getenv("PUBLIC_BASE_URL")

    # Email / SMTP (legacy path — DigitalOcean blocks outbound port 587 on new
    # droplets, so SMTP rarely works in prod. Kept as fallback for local dev.)
    SMTP_HOST: str = os.getenv("SMTP_HOST") or "smtp.gmail.com"
    SMTP_PORT: int = int(os.getenv("SMTP_PORT") or "587")
    SMTP_USER: str | None = os.getenv("SMTP_USER") or None
    SMTP_PASSWORD: str | None = os.getenv("SMTP_PASSWORD") or None
    SMTP_FROM: str = os.getenv("SMTP_FROM") or "MarketPulse <noreply@marketpulse.app>"

    # Email via Resend HTTP API (resend.com) — preferred path on DO/cloud where
    # SMTP egress is blocked. If RESEND_API_KEY is set, email_sender uses it
    # instead of aiosmtplib. Sign-up is free (100 emails/day, no credit card).
    RESEND_API_KEY: str | None = os.getenv("RESEND_API_KEY") or None
    # Sender address. For unverified domains Resend lets you send only via
    # `onboarding@resend.dev`. Set this to your verified domain sender once you
    # verify a domain.
    RESEND_FROM: str = os.getenv("RESEND_FROM") or "MarketPulse <onboarding@resend.dev>"

    # Distributed worker (S19.5) — server enqueues scrape jobs in Redis,
    # local worker (on user's machine, residential IP) polls + executes + POSTs
    # results back. WORKER_TOKEN is a shared secret for worker→server auth.
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    WORKER_TOKEN: str | None = os.getenv("WORKER_TOKEN")

    # Check that key is loaded
    def validate(self):
        if not self.GOOGLE_API_KEY:
            raise ValueError("ERROR: GOOGLE_API_KEY not found in .env file")

# Create single instance of settings
settings = Settings()