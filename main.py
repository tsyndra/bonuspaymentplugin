import os
import re
import asyncio
import requests
from telegram import Bot
from telegram.error import TelegramError
from datetime import datetime, date, time
import json
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler
import textwrap
import aiohttp
import sys
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger


class IikoReporter:
    load_dotenv()

    def __init__(self):
        # Инициализация параметров из переменных окружения
        self.api_key = os.getenv('IIKO_API_KEY')
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.target_org_id = os.getenv('TARGET_ORG_ID')
        
        if not all([self.api_key, self.telegram_token, self.chat_id]):
            raise ValueError("Не заданы обязательные переменные окружения")
        
        self.bot = Bot(token=self.telegram_token)
        self.nomenclature_cache_file = "nomenclature_cache.json"
        self.nomenclature_cache_date_file = "nomenclature_cache_date.txt"
        self.aiohttp_session = None
        
        # Инициализация планировщика
        self.scheduler = AsyncIOScheduler(timezone=pytz.timezone('Europe/Moscow'))
        self._setup_scheduler()

    def _setup_scheduler(self):
        """Настройка планировщика задач"""
        # Добавляем задачу отправки стоп-листа каждый час с 11:00 по 22:00
        for hour in range(11, 23):  # 11:00 - 22:00
            self.scheduler.add_job(
                self._send_scheduled_report,
                CronTrigger(hour=hour, minute=0),
                id=f'stoplist_report_{hour}',
                name=f'Отправка стоп-листа в {hour}:00',
                replace_existing=True
            )
        
        print(f"Планировщик настроен: отправка стоп-листа каждый час с 11:00 по 22:00 по МСК")
        
        # Запускаем планировщик
        self.scheduler.start()
        print("Планировщик запущен")

    async def _send_scheduled_report(self):
        """Отправка запланированного отчета"""
        try:
            print(f"🕐 Выполнение запланированной отправки стоп-листа в {datetime.now(pytz.timezone('Europe/Moscow')).strftime('%H:%M')}")
            await self.run_report()
        except Exception as e:
            error_msg = f"❌ Ошибка при выполнении запланированной отправки: {str(e)}"
            print(error_msg)
            await self.send_telegram_message(error_msg)

    def is_nomenclature_cache_valid(self):
        """Проверяет, актуален ли кэш номенклатуры (обновляется раз в день в полночь)."""
        try:
            if not os.path.exists(self.nomenclature_cache_date_file):
                return False
                
            with open(self.nomenclature_cache_date_file, 'r') as f:
                cache_date = date.fromisoformat(f.read().strip())
                
            return cache_date == date.today()
        except Exception:
            return False

    def save_nomenclature_cache(self, data):
        """Сохраняет номенклатуру в кэш."""
        try:
            with open(self.nomenclature_cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            with open(self.nomenclature_cache_date_file, 'w') as f:
                f.write(date.today().isoformat())
            print("Номенклатура сохранена в кэш")
        except Exception as e:
            print(f"Ошибка при сохранении кэша номенклатуры: {str(e)}")

    def load_nomenclature_cache(self):
        """Загружает номенклатуру из кэша."""
        try:
            with open(self.nomenclature_cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Ошибка при загрузке кэша номенклатуры: {str(e)}")
            return None

    async def get_aiohttp_session(self):
        if self.aiohttp_session is None or self.aiohttp_session.closed:
            self.aiohttp_session = aiohttp.ClientSession()
        return self.aiohttp_session

    async def get_access_token(self):
        """Получение токена доступа iiko."""
        url = "https://api-ru.iiko.services/api/1/access_token"
        headers = {"Content-Type": "application/json"}
        data = {"apiLogin": self.api_key}
        session = await self.get_aiohttp_session()
        try:
            async with session.post(url, json=data, headers=headers) as response:
                response.raise_for_status()
                resp_json = await response.json()
                return resp_json.get("token")
        except Exception as e:
            raise Exception(f"Ошибка получения токена: {str(e)}")

    async def get_organizations(self, token):
        """Получение списка организаций."""
        url = "https://api-ru.iiko.services/api/1/organizations"
        headers = {"Authorization": f"Bearer {token}"}
        session = await self.get_aiohttp_session()
        try:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                data = await response.json()
                return data if isinstance(data, list) else data.get("organizations", [])
        except Exception as e:
            raise Exception(f"Ошибка получения организаций: {str(e)}")

    async def get_stop_list(self, token, organization_id):
        """Получение стоп-листа организации."""
        url = "https://api-ru.iiko.services/api/1/stop_lists"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {"organizationIds": [organization_id]}
        session = await self.get_aiohttp_session()
        try:
            async with session.post(url, json=payload, headers=headers) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            raise Exception(f"Ошибка получения стоп-листа: {str(e)}")

    async def get_products_info(self, token, product_ids):
        """Получение информации о продуктах с использованием кэша."""
        # Проверяем кэш
        if self.is_nomenclature_cache_valid():
            print("Используем кэшированную номенклатуру")
            return self.load_nomenclature_cache()

        print("Получение актуальной номенклатуры...")
        url = "https://api-ru.iiko.services/api/1/nomenclature"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        session = await self.get_aiohttp_session()
        # Разбиваем список продуктов на части по 50 штук
        chunk_size = 50
        all_products = []
        all_categories = []
        async def make_request(chunk, attempt=1):
            max_attempts = 3
            base_delay = 2  # базовая задержка 2 секунды
            while attempt <= max_attempts:
                try:
                    payload = {
                        "organizationId": self.target_org_id,
                        "productIds": chunk
                    }
                    if attempt > 1:
                        delay = base_delay * (2 ** (attempt - 1))
                        print(f"Повторная попытка {attempt} для чанка {chunk[0]}-{chunk[-1]}, задержка {delay}с")
                        await asyncio.sleep(delay)
                    async with session.post(url, json=payload, headers=headers) as response:
                        response.raise_for_status()
                        return await response.json()
                except Exception as e:
                    if attempt == max_attempts:
                        print(f"Все попытки исчерпаны для чанка {chunk[0]}-{chunk[-1]}: {str(e)}")
                        return None
                    attempt += 1
                    continue
        for i in range(0, len(product_ids), chunk_size):
            chunk = product_ids[i:i + chunk_size]
            if i > 0:
                await asyncio.sleep(2)
            data = await make_request(chunk)
            if data:
                all_categories.extend(data.get("productCategories", []))
                all_products.extend(data.get("products", []))
        result = {
            "productCategories": all_categories,
            "products": all_products
        }
        # Сохраняем в кэш
        self.save_nomenclature_cache(result)
        return result

    def extract_org_number(self, org_name):
        """Извлечение номера из названия организации."""
        # Ищем паттерн "число. название" в начале строки
        match = re.match(r'^(\d+)\.\s*', org_name)
        if match:
            return int(match.group(1))
        # Если нет паттерна "число.", ищем любое число в названии
        numbers = re.findall(r'\d+', org_name)
        return int(numbers[0]) if numbers else 0

    async def send_telegram_message(self, text):
        """Отправка сообщения в Telegram."""
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text
            )
            return True
        except TelegramError as e:
            print(f"Ошибка отправки сообщения: {str(e)}")
            return False

    async def run_report(self, update=None):
        try:
            print("Начало формирования отчета...")
            
            # Получаем токен и организации
            token = await self.get_access_token()
            organizations = await self.get_organizations(token)
            
            # Собираем данные по организациям и стоп-листам
            all_product_ids = set()
            org_data = {}
            
            print("Получение данных по организациям...")
            for org in organizations:
                if not isinstance(org, dict):
                    continue
                    
                org_id = org.get("id")
                org_name = org.get("name")
                
                if not org_id or not org_name:
                    continue
                    
                stop_list = await self.get_stop_list(token, org_id)
                items = []
                
                for group in stop_list.get("terminalGroupStopLists", []):
                    for terminal in group.get("items", []):
                        items.extend([item for item in terminal.get("items", []) 
                                    if isinstance(item, dict) and item.get("balance", 1) == 0])
                
                org_data[org_id] = {
                    "name": org_name,
                    "items": items
                }
                all_product_ids.update(item["productId"] for item in items 
                                     if isinstance(item, dict) and "productId" in item)
            
            print("Получение информации о продуктах...")
            # Получаем информацию о продуктах
            products_info = {}
            category_id_to_name = {}
            if all_product_ids:
                products_response = await self.get_products_info(token, list(all_product_ids))
                for cat in products_response.get("productCategories", []):
                    category_id_to_name[cat["id"]] = cat["name"].lower()
                for p in products_response.get("products", []):
                    products_info[p["id"]] = {
                        "name": p["name"],
                        "category": category_id_to_name.get(p.get("productCategoryId", None), "")
                    }
            
            print("Формирование отчетов...")
            # Формируем отчетные данные
            exclude_categories = [
                "десерты", "десерты понедельник", "десерты вторник", 
                "десерты среда", "десерты четверг", "пиво", "соусы"
            ]
            exclude_orgs = ["кожуховская", "рязань"]
            
            # Группируем данные по организациям
            org_reports = {}
            
            for org_id, data in org_data.items():
                org_name_lower = data["name"].lower()
                if any(ex in org_name_lower for ex in exclude_orgs):
                    continue
                    
                org_products = []
                for item in data["items"]:
                    if not isinstance(item, dict):
                        continue
                        
                    prod = products_info.get(item.get("productId"))
                    if not prod:
                        continue  # Пропускаем неизвестные продукты
                        
                    product_name = prod["name"]
                    category = prod["category"]
                        
                    if category in exclude_categories:
                        continue
                    if category == "напитки" and "морс" not in product_name.lower():
                        continue
                        
                    org_products.append(product_name)
                    
                if org_products:
                    org_reports[data["name"]] = org_products
            
            if not org_reports:
                if update:
                    await update.message.reply_text("Нет данных для отчета")
                else:
                    await self.send_telegram_message("Нет данных для отчета")
                return
            
            print("Отправка отчетов...")
            # Формируем текстовый отчет
            report_text = "📋 Отчет по стоп-листам:\n\n"
            
            # Сортируем филиалы по номеру
            sorted_orgs = sorted(org_reports.items(), key=lambda x: self.extract_org_number(x[0]))
            
            for org_name, products in sorted_orgs:
                report_text += f"🏪 {org_name}:\n"
                for product in products:
                    report_text += f"• {product}\n"
                report_text += "\n"
            
            # Разбиваем на части, если сообщение слишком длинное
            max_length = 4096
            if len(report_text) > max_length:
                parts = []
                current_part = ""
                for line in report_text.split('\n'):
                    if len(current_part + line + '\n') > max_length:
                        if current_part:
                            parts.append(current_part.strip())
                        current_part = line + '\n'
                    else:
                        current_part += line + '\n'
                if current_part:
                    parts.append(current_part.strip())
                
                for i, part in enumerate(parts):
                    if update:
                        await update.message.reply_text(part)
                    else:
                        await self.send_telegram_message(part)
            else:
                if update:
                    await update.message.reply_text(report_text)
                else:
                    await self.send_telegram_message(report_text)
            
            print("Отчет успешно отправлен")
            
        except Exception as e:
            error_msg = f"Ошибка при формировании отчета: {str(e)}"
            print(error_msg)
            if update:
                await update.message.reply_text(error_msg)
            else:
                await self.send_telegram_message(error_msg)

    async def close(self):
        """Закрытие соединений и остановка планировщика"""
        if self.aiohttp_session and not self.aiohttp_session.closed:
            await self.aiohttp_session.close()
        
        # Останавливаем планировщик
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("Планировщик остановлен")

async def report_command(update, context):
    await update.message.reply_text("Формирую отчет...")
    await context.bot_data['reporter'].run_report(update)

async def help_command(update, context):
    await update.message.reply_text(
        "/report — сформировать отчет\n"
        "/schedule — показать запланированные задачи\n"
        "/help — справка\n"
        "/ping — проверить, что бот работает\n\n"
        "📅 **Автоматическая отправка:**\n"
        "Стоп-лист отправляется каждый час с 11:00 по 22:00 по МСК"
    )

async def ping_command(update, context):
    await update.message.reply_text("Бот работает!")

async def schedule_command(update, context):
    """Проверка статуса планировщика"""
    reporter = context.bot_data['reporter']
    jobs = reporter.scheduler.get_jobs()
    
    if jobs:
        schedule_text = "📅 **Запланированные задачи:**\n\n"
        for job in jobs:
            next_run = job.next_run_time.strftime('%d.%m.%Y %H:%M:%S') if job.next_run_time else 'Не запланировано'
            schedule_text += f"• {job.name}\n   Следующий запуск: {next_run}\n\n"
    else:
        schedule_text = "📅 Нет запланированных задач"
    
    await update.message.reply_text(schedule_text, parse_mode='Markdown')

if __name__ == "__main__":
    import asyncio
    reporter = IikoReporter()
    # Проверка переменных окружения
    print("IIKO_API_KEY:", 'OK' if reporter.api_key else 'NOT SET')
    print("TELEGRAM_BOT_TOKEN:", 'OK' if reporter.telegram_token else 'NOT SET')
    print("TELEGRAM_CHAT_ID:", 'OK' if reporter.chat_id else 'NOT SET')
    print("TARGET_ORG_ID:", 'OK' if reporter.target_org_id else 'NOT SET')
    if not all([reporter.api_key, reporter.telegram_token, reporter.chat_id, reporter.target_org_id]):
        print("Ошибка: Не все переменные окружения заданы. Проверьте .env файл или переменные окружения.")
        sys.exit(1)
    # Проверка токена Telegram (простая)
    if not reporter.telegram_token or not reporter.telegram_token.startswith('5'):
        print("Внимание: Telegram токен выглядит некорректно. Проверьте его в .env!")
    application = Application.builder().token(reporter.telegram_token).build()
    application.bot_data['reporter'] = reporter
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ping", ping_command))
    application.add_handler(CommandHandler("schedule", schedule_command))
    print("Запуск polling...")
    try:
        application.run_polling()
    except Exception as e:
        print(f"Ошибка при запуске polling: {e}")
    finally:
        print("Polling завершён, закрытие сессии...")
        asyncio.run(reporter.close())