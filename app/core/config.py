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

    # Delays between paginated page loads (seconds)
    PAGE_DELAY_MIN: float = 2.0
    PAGE_DELAY_MAX: float = 5.0

    # Cooldown when a 429 / 503 rate-limit response is received (seconds)
    RATE_LIMIT_COOLDOWN_MIN: float = 30.0
    RATE_LIMIT_COOLDOWN_MAX: float = 60.0
    
    # Check that key is loaded
    def validate(self):
        if not self.GOOGLE_API_KEY:
            raise ValueError("ERROR: GOOGLE_API_KEY not found in .env file")

# Create single instance of settings
settings = Settings()