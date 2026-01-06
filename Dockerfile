# Используем Python 3.11
FROM python:3.11-slim

# Устанавливаем системные пакеты (нужны для Postgres и Playwright)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Сначала копируем зависимости (кэширование Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем браузеры для Playwright
RUN playwright install --with-deps chromium

# Копируем весь код проекта
COPY . .

# Команда запуска
CMD ["python", "-m", "app.main"]