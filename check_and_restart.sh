#!/bin/bash
set -euo pipefail

# Скрипт для проверки и перезапуска iiko-reporter бота
# Запускается через cron каждые 5 минут

CONTAINER_NAME="${CONTAINER_NAME:-iiko-reporter}"
WORKDIR="${WORKDIR:-/home/workdir/iiko-reporter}"
COMPOSE="docker compose"

cd "$WORKDIR" || exit 1

# Проверяем, запущен ли контейнер
if ! docker ps --format "{{.Names}}" | grep -qx "$CONTAINER_NAME"; then
    echo "$(date): Контейнер $CONTAINER_NAME не запущен. Перезапускаем..."
    
    # Останавливаем все контейнеры проекта
    $COMPOSE down
    
    # Запускаем заново
    $COMPOSE up -d
    
    # Проверяем, что запустился
    sleep 10
    if docker ps --format "{{.Names}}" | grep -qx "$CONTAINER_NAME"; then
        echo "$(date): ✅ Контейнер успешно перезапущен"
    else
        echo "$(date): ❌ Ошибка при перезапуске контейнера"
        exit 1
    fi
else
    echo "$(date): ✅ Контейнер $CONTAINER_NAME работает нормально"
fi
