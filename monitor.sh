#!/bin/bash
set -euo pipefail

CONTAINER_NAME="${CONTAINER_NAME:-iiko-reporter}"

echo "=== Мониторинг iiko-reporter бота ==="
echo "Время: $(date)"
echo

# Проверяем статус контейнера
echo "📊 Статус контейнера:"
docker ps --filter "name=^/${CONTAINER_NAME}$" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo

# Проверяем последние логи
echo "📋 Последние логи (последние 5 строк):"
docker logs "$CONTAINER_NAME" --tail 5 2>/dev/null || echo "Контейнер не найден"

echo

# Проверяем health check
echo "🏥 Health check статус:"
docker inspect "$CONTAINER_NAME" --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}unconfigured{{end}}' 2>/dev/null || echo "Health check недоступен"

echo
echo "=== Конец мониторинга ==="
