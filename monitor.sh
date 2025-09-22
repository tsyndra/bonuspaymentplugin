#!/bin/bash

echo "=== Мониторинг iiko-reporter бота ==="
echo "Время: $(date)"
echo

# Проверяем статус контейнера
echo "📊 Статус контейнера:"
docker ps --filter "name=iiko-reporter" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo

# Проверяем последние логи
echo "📋 Последние логи (последние 5 строк):"
docker logs iiko-reporter_server_1 --tail 5 2>/dev/null || echo "Контейнер не найден"

echo

# Проверяем health check
echo "🏥 Health check статус:"
docker inspect iiko-reporter_server_1 --format='{{.State.Health.Status}}' 2>/dev/null || echo "Health check недоступен"

echo
echo "=== Конец мониторинга ==="
