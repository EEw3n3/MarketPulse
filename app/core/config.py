import os
from dotenv import load_dotenv

# Load variables from .env file into memory
load_dotenv()

class Settings:
    PROJECT_NAME: str = "MarketPulse"
    VERSION: str = "1.2.0"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///database.db"
    
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini") # If env is empty, take 4o-mini

    # Check that key is loaded
    def validate(self):
        if not self.OPENAI_API_KEY:
            raise ValueError("ERROR: OPENAI_API_KEY not found in .env file")

# Create single instance of settings
settings = Settings()