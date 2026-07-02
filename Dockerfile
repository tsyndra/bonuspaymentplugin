FROM python:3.10

WORKDIR /app

# Установка системных зависимостей для pandas, matplotlib, pillow и Playwright
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    libffi-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libfreetype6-dev \
    libpng-dev \
    wget \
    gnupg \
    libnspr4 \
    libnss3 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    fonts-unifont \
    && rm -rf /var/lib/apt/lists/*

# Копирование и установка Python-зависимостей
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install wheel && \
    pip install --no-cache-dir -r requirements.txt

# Установка браузеров для Playwright
RUN playwright install chromium

COPY . .

# Запуск в режиме демона для постоянной работы
CMD ["python", "-u", "main.py"]