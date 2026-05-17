# Используем Python 3.11
FROM python:3.11-slim

# Устанавливаем системные пакеты (нужны для Postgres и Playwright)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Сначала копируем зависимости (кэширование Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем браузеры для Playwright:
#   - bundled chromium  (fallback, headless)
#   - real Google Chrome via Playwright's channel installer
# Real Chrome имеет реальные plugins/codecs/WebGL fingerprint и заметно лучше
# обходит Cloudflare Managed Challenge (1a.lv). channel="chrome" в browser.py
# использует именно эту установку.
RUN playwright install --with-deps chromium
RUN playwright install --with-deps chrome

# Копируем весь код проекта
COPY . .

# Команда запуска
CMD ["python", "-m", "app.main"]