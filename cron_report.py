#!/usr/bin/env python3
"""
Отправка отчетов в новый чат и скриншотов таблицы для cron
Основные отчеты отправляются планировщиком в main.py
"""
import asyncio
import os
import sys
from main import IikoReporter
from dotenv import load_dotenv
from datetime import datetime
import pytz

async def send_scheduled_report():
    """Отправка запланированного отчета"""
    load_dotenv()
    
    # Получаем текущее время МСК
    msk_tz = pytz.timezone('Europe/Moscow')
    now = datetime.now(msk_tz)
    current_hour = now.hour
    
    print(f"🕐 Запуск отправки отчета в {now.strftime('%Y-%m-%d %H:%M:%S')} МСК")
    
    # Создаем экземпляр репортера
    reporter = IikoReporter()
    
    try:
        # Отправляем в новый чат в 12:00 и 17:00
        if current_hour in [12, 17]:
            print(f"📤 Отправляем отчет в новый чат: {reporter.new_chat_id}")
            await reporter.run_report(target_chat_id=reporter.new_chat_id)
            print("✅ Отчет успешно отправлен в новый чат!")
        
        # Отправляем скриншот таблицы в указанные часы
        if current_hour in [12, 17, 18, 19, 20, 21]:
            print(f"📸 Отправляем скриншот таблицы в новый чат: {reporter.new_chat_id}")
            await reporter.send_table_screenshot()
            print("✅ Скриншот таблицы успешно отправлен!")
        
        if not (current_hour in [12, 17, 18, 19, 20, 21]):
            print("⏭️ Не время для отправки отчетов")
        
    except Exception as e:
        print(f"❌ Ошибка при отправке отчета: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Закрываем соединения
        await reporter.close()

if __name__ == "__main__":
    asyncio.run(send_scheduled_report())
