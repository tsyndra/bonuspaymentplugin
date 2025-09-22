#!/bin/bash

# Скрипт для проверки и перезапуска iiko-reporter бота
# Запускается через cron каждые 5 минут

CONTAINER_NAME="iiko-reporter_server_1"
WORKDIR="/home/workdir/iiko-reporter"

cd "$WORKDIR" || exit 1

# Проверяем, запущен ли контейнер
if ! docker ps --format "table {{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
    echo "$(date): Контейнер $CONTAINER_NAME не запущен. Перезапускаем..."
    
    # Останавливаем все контейнеры проекта
    docker-compose down
    
    # Запускаем заново
    docker-compose up -d
    
    # Проверяем, что запустился
    sleep 10
    if docker ps --format "table {{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        echo "$(date): ✅ Контейнер успешно перезапущен"
    else
        echo "$(date): ❌ Ошибка при перезапуске контейнера"
        exit 1
    fi
else
    echo "$(date): ✅ Контейнер $CONTAINER_NAME работает нормально"
fi
