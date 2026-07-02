#!/usr/bin/env python3
"""
Тестовый скрипт для отправки скриншота таблицы
"""
import asyncio
import os
from main import IikoReporter
from dotenv import load_dotenv
from datetime import datetime
import pytz

async def test_table_screenshot():
    """Тестовая отправка скриншота таблицы"""
    load_dotenv()
    
    # Получаем текущее время МСК
    msk_tz = pytz.timezone('Europe/Moscow')
    now = datetime.now(msk_tz)
    
    print(f"📸 Тестовая отправка скриншота таблицы в {now.strftime('%Y-%m-%d %H:%M:%S')} МСК")
    
    # Создаем экземпляр репортера
    reporter = IikoReporter()
    
    try:
        print(f"📸 Отправляем скриншот таблицы в новый чат: {reporter.new_chat_id}")
        await reporter.send_table_screenshot()
        print("✅ Скриншот таблицы успешно отправлен!")
        
    except Exception as e:
        print(f"❌ Ошибка при отправке скриншота таблицы: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Закрываем соединения
        await reporter.close()

if __name__ == "__main__":
    asyncio.run(test_table_screenshot())
