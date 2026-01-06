import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла в память
load_dotenv()

class Settings:
    # База данных
    DATABASE_URL: str = "sqlite+aiosqlite:///database.db"
    
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini") # Если в env пусто, возьмет 4o-mini

    # Проверка, что ключ загрузился
    def validate(self):
        if not self.OPENAI_API_KEY:
            raise ValueError("ОШИБКА: Не найден OPENAI_API_KEY в файле .env")

# Создаем единственный экземпляр настроек
settings = Settings()