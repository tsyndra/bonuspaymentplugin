# Мониторинг iiko-reporter бота

## Текущий статус

Бот был настроен с автоматическим перезапуском после простоя с 15 августа.

## Настроенные механизмы защиты

### 1. Docker Compose с политикой restart
- `restart: unless-stopped` - автоматический перезапуск при сбоях
- Health check каждые 30 секунд
- Проверка процесса main.py

### 2. Cron задача
- Проверка каждые 5 минут
- Автоматический перезапуск при необходимости
- Логирование в `bot_monitor.log`

### 3. Скрипты мониторинга

#### `monitor.sh` - текущий статус
```bash
./monitor.sh
```

#### `check_and_restart.sh` - проверка и перезапуск
```bash
./check_and_restart.sh
```

## Логи

- **Логи бота**: `docker logs iiko-reporter`
- **Логи мониторинга**: `tail -f bot_monitor.log`

## Команды управления

```bash
# Запуск
docker compose up -d

# Остановка
docker compose down

# Перезапуск
docker compose restart

# Просмотр статуса
docker ps | grep iiko

# Просмотр логов
docker logs -f iiko-reporter
```

## Расписание работы

- **Отправка стоп-листа**: только в 12:00 и 17:00 по МСК (только новый чат)
- **Скриншоты таблицы**: 12:00, 17:00, 18:00, 19:00, 20:00, 21:00, 21:30, 22:00 по МСК (новый чат)
- **Обновление кеша**: каждый день в 00:00 по МСК
- **Проверка мониторинга**: каждые 5 минут

## Устранение неполадок

1. Если бот не отвечает:
   ```bash
   ./check_and_restart.sh
   ```

2. Если нужно принудительный перезапуск:
   ```bash
   docker compose down && docker compose up -d
   ```

3. Проверка переменных окружения:
   ```bash
   docker exec iiko-reporter env | grep -E "(TELEGRAM|IIKO|TABLE_SCREENSHOT)"
   ```
