import sys
print('DEBUG sys.argv:', sys.argv)
import os
import re
import asyncio
import requests
from telegram import Bot
from telegram.error import TelegramError
from datetime import datetime, date, time, timedelta
import json
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler
import textwrap
import aiohttp
import pytz
from time import sleep
import signal
from table_screenshot import create_table_screenshot


class IikoReporter:
    def __init__(self):
        # Инициализация параметров из переменных окружения
        self.api_key = os.getenv('IIKO_API_KEY')
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.new_chat_id = os.getenv('TELEGRAM_NEW_CHAT_ID', '-1001507942384')
        
        if not all([self.api_key, self.telegram_token, self.chat_id]):
            raise ValueError("Не заданы обязательные переменные окружения")
        
        print(f"Основной чат ID: {self.chat_id}")
        print(f"Новый чат ID: {self.new_chat_id}")
        
        self.bot = Bot(token=self.telegram_token)
        self.nomenclature_cache_file = "nomenclature_cache.json"
        self.nomenclature_cache_date_file = "nomenclature_cache_date.txt"
        self.aiohttp_session = None
        
        # Флаг для остановки планировщика
        self.scheduler_running = False
        self.scheduler_task = None
        
        # Отслеживание отправленных сообщений в новый чат
        self.new_chat_sent_today = set()

    async def start_scheduler(self):
        """Запуск планировщика в отдельной задаче"""
        if not self.scheduler_running:
            self.scheduler_running = True
            # Запускаем планировщик напрямую, а не как task
            print("Планировщик запущен")
            await self._scheduler_loop()

    async def stop_scheduler(self):
        """Остановка планировщика"""
        if self.scheduler_running:
            self.scheduler_running = False
            if self.scheduler_task and not self.scheduler_task.done():
                try:
                    self.scheduler_task.cancel()
                    await self.scheduler_task
                except asyncio.CancelledError:
                    pass
                except RuntimeError as e:
                    if "Event loop is closed" not in str(e):
                        print(f"Ошибка при остановке планировщика: {e}")
            print("Планировщик остановлен")

    async def _scheduler_loop(self):
        """Основной цикл планировщика"""
        print("🕐 Планировщик запущен: отправка стоп-листа каждый час с 11:00 по 22:00 по МСК")
        print("🕐 Дополнительная отправка в новый чат в 12:00 и 17:00 по МСК")
        print("📸 Отправка скриншотов таблицы в 12:00, 17:00, 18:00, 19:00, 20:00, 21:00 по МСК")
        print("🕐 Обновление кеша номенклатуры каждый день в 00:00 по МСК")
        
        msk_tz = pytz.timezone('Europe/Moscow')
        last_cache_update_date = None
        startup_check_done = False
        last_date = None
        
        while self.scheduler_running:
            try:
                now = datetime.now(msk_tz)
                current_hour = now.hour
                current_minute = now.minute
                current_date = now.date()
                
                # Сбрасываем отслеживание отправленных сообщений в новый день
                if last_date is not None and last_date != current_date:
                    self.new_chat_sent_today.clear()
                    print(f"🔄 Новый день: сбрасываем отслеживание отправленных сообщений в новый чат")
                last_date = current_date
                
                # Проверяем кэш при первом запуске планировщика (через 1 минуту)
                if not startup_check_done:
                    startup_check_done = True
                    print(f"🔄 Первоначальная проверка кэша номенклатуры в {now.strftime('%Y-%m-%d %H:%M:%S')} МСК...")
                    if not self.is_nomenclature_cache_valid():
                        print("🔄 Кэш номенклатуры устарел при запуске планировщика, обновляем...")
                        try:
                            await self._update_nomenclature_cache()
                            last_cache_update_date = current_date
                            print("✅ Кэш номенклатуры обновлен при запуске планировщика")
                        except Exception as e:
                            print(f"❌ Ошибка при обновлении кэша при запуске: {str(e)}")
                    else:
                        print("✅ Кэш номенклатуры актуален при запуске планировщика")
                
                # Проверяем, нужно ли отправить отчет (каждый час с 11 до 22)
                # Исключаем 12:00 и 17:00, так как для них есть отдельная логика
                if 11 <= current_hour <= 22 and current_minute == 0 and current_hour not in [12, 17]:
                    print(f"🕐 Выполнение запланированной отправки стоп-листа в {now.strftime('%Y-%m-%d %H:%M:%S')} МСК")
                    await self._send_scheduled_report()
                
                # Проверяем, нужно ли отправить отчет в новый чат (12:00 и 17:00)
                if current_hour in [12, 17] and current_minute == 0 and current_hour not in self.new_chat_sent_today:
                    print(f"🕐 УСЛОВИЕ СРАБОТАЛО: час={current_hour}, минута={current_minute}")
                    print(f"🕐 Выполнение дополнительной отправки стоп-листа в новый чат в {now.strftime('%Y-%m-%d %H:%M:%S')} МСК")
                    await self._send_scheduled_report_to_new_chat()
                    self.new_chat_sent_today.add(current_hour)
                    print(f"✅ Отправка в новый чат в {current_hour}:00 отмечена как выполненная")
                
                # Проверяем, нужно ли отправить скриншот таблицы (12, 17, 18, 19, 20, 21)
                table_screenshot_hours = [12, 17, 18, 19, 20, 21]
                if current_hour in table_screenshot_hours and current_minute == 0:
                    print(f"📸 Выполнение отправки скриншота таблицы в {now.strftime('%Y-%m-%d %H:%M:%S')} МСК")
                    await self.send_table_screenshot()
                
                # Проверяем, нужно ли обновить кеш (в полночь или если кеш устарел)
                should_update_cache = False
                
                # Обновляем в полночь (00:00-00:05)
                if current_hour == 0 and current_minute <= 5:
                    if last_cache_update_date != current_date:
                        should_update_cache = True
                        print(f"🕐 Запланированное обновление кеша номенклатуры в {now.strftime('%Y-%m-%d %H:%M:%S')} МСК")
                
                # Принудительно обновляем, если кеш устарел
                elif not self.is_nomenclature_cache_valid() and last_cache_update_date != current_date:
                    should_update_cache = True
                    print(f"🕐 Принудительное обновление устаревшего кеша номенклатуры в {now.strftime('%Y-%m-%d %H:%M:%S')} МСК")
                
                if should_update_cache:
                    await self._update_nomenclature_cache()
                    last_cache_update_date = current_date
                
                # Ждем до следующей минуты
                now = datetime.now(msk_tz)
                next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
                sleep_seconds = (next_minute - now).total_seconds()
                
                if sleep_seconds > 0:
                    print(f"🕐 Планировщик ждет {sleep_seconds:.1f} секунд до следующей проверки ({next_minute.strftime('%H:%M:%S')} МСК)...")
                    await asyncio.sleep(sleep_seconds)
                else:
                    # Если sleep_seconds <= 0, ждем 1 секунду
                    print(f"🕐 Планировщик ждет 1 секунду до следующей проверки...")
                    await asyncio.sleep(1)
                    
            except asyncio.CancelledError:
                print("Планировщик остановлен")
                break
            except Exception as e:
                error_msg = f"❌ Ошибка в планировщике: {str(e)}"
                print(error_msg)
                # НЕ отправляем ошибки планировщика в чат - только логируем
                # Ждем минуту перед повторной попыткой
                await asyncio.sleep(60)

    async def _send_scheduled_report(self):
        """Отправка запланированного отчета"""
        try:
            moscow_time = datetime.now(pytz.timezone('Europe/Moscow'))
            print(f"🕐 Выполнение запланированной отправки стоп-листа в {moscow_time.strftime('%Y-%m-%d %H:%M:%S')} МСК")
            print(f"🕐 UTC время: {datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S')}")
            
            await self.run_report()
            print(f"✅ Запланированная отправка стоп-листа завершена успешно")
        except Exception as e:
            error_msg = f"❌ Ошибка при выполнении запланированной отправки: {str(e)}"
            print(error_msg)
            # НЕ отправляем ошибки в чат - только логируем

    async def _send_scheduled_report_to_new_chat(self):
        """Отправка запланированного отчета в новый чат"""
        try:
            moscow_time = datetime.now(pytz.timezone('Europe/Moscow'))
            print(f"🕐 Выполнение дополнительной отправки стоп-листа в новый чат в {moscow_time.strftime('%Y-%m-%d %H:%M:%S')} МСК")
            print(f"🕐 UTC время: {datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"🕐 Целевой чат ID: {self.new_chat_id}")
            
            await self.run_report(target_chat_id=self.new_chat_id)
            print(f"✅ Дополнительная отправка стоп-листа в новый чат завершена успешно")
        except Exception as e:
            error_msg = f"❌ Ошибка при выполнении дополнительной отправки в новый чат: {str(e)}"
            print(error_msg)
            # НЕ отправляем ошибки в чат - только логируем

    async def _update_nomenclature_cache(self):
        """Обновление кеша номенклатуры в полночь"""
        try:
            print(f"🕐 Обновление кеша номенклатуры в {datetime.now(pytz.timezone('Europe/Moscow')).strftime('%H:%M')}")
            # Принудительно обновляем кеш, удаляя файл с датой
            if os.path.exists(self.nomenclature_cache_date_file):
                os.remove(self.nomenclature_cache_date_file)
                print("Файл даты кеша удален для принудительного обновления")
            
            # Получаем токен и организации
            token = await self.get_access_token()
            organizations = await self.get_organizations(token)
            
            # Находим организацию "Скандинавия"
            scandinavia_org = None
            for org in organizations:
                if isinstance(org, dict) and "Скандинавия" in org.get("name", ""):
                    scandinavia_org = org
                    break
            
            if not scandinavia_org:
                raise Exception("Не найдена организация 'Скандинавия' для обновления кеша")
            
            print(f"Обновляем кеш номенклатуры по организации: {scandinavia_org['name']}")
            
            # Обновляем кеш, получая всю номенклатуру по Скандинавии
            await self.get_products_info(token, [], organization_id=scandinavia_org["id"])
            print("Кеш номенклатуры успешно обновлен")
                
        except Exception as e:
            error_msg = f"❌ Ошибка при обновлении кеша номенклатуры: {str(e)}"
            print(error_msg)
            # НЕ отправляем ошибки в чат - только логируем

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

    async def get_products_info(self, token, product_ids, organization_id=None, force_update=False):
        """Получение информации о продуктах с использованием кэша."""
        # Проверяем кэш, если не требуется принудительное обновление
        if not force_update and self.is_nomenclature_cache_valid():
            print("Используем кэшированную номенклатуру")
            return self.load_nomenclature_cache()

        if force_update:
            print("Принудительное обновление номенклатуры...")
        else:
            print("Получение актуальной номенклатуры...")
        
        # Получаем организации и находим "Колл центр"
        organizations = await self.get_organizations(token)
        if not organizations:
            raise Exception("Не удалось получить организации")
        
        # Ищем организацию "Колл центр"
        call_center_org = None
        for org in organizations:
            if isinstance(org, dict) and "Колл центр" in org.get("name", ""):
                call_center_org = org
                break
        
        if not call_center_org:
            raise Exception("Не найдена организация 'Колл центр'")
        
        print(f"Используем организацию: {call_center_org['name']}")
        
        url = "https://api-ru.iiko.services/api/1/nomenclature"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        session = await self.get_aiohttp_session()
        
        # Если product_ids пустой, получаем всю номенклатуру из Колл центра
        if not product_ids:
            print("Получение полной номенклатуры из Колл центра...")
            
            payload = {"organizationId": call_center_org["id"]}
            try:
                async with session.post(url, json=payload, headers=headers) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    products = data.get("products", [])
                    categories = data.get("productCategories", [])
                    
                    print(f"📊 Получено товаров: {len(products)}")
                    print(f"📊 Получено категорий: {len(categories)}")
                    
                    # Проверяем, есть ли эмпанадас
                    for product in products:
                        if 'эмпанадас' in product.get('name', '').lower() or 'чебуреки' in product.get('name', '').lower():
                            print(f"🎯 НАЙДЕН ЭМПАНАДАС: {product['name']} (ID: {product['id']})")
                    
                    result = {
                        "productCategories": categories,
                        "products": products
                    }
                    # Сохраняем в кэш
                    self.save_nomenclature_cache(result)
                    return result
            except Exception as e:
                raise Exception(f"Ошибка получения номенклатуры: {str(e)}")
        
        # Если есть product_ids, разбиваем на чанки
        chunk_size = 50
        all_products = []
        all_categories = []
        async def make_request(chunk, attempt=1):
            max_attempts = 3
            base_delay = 2  # базовая задержка 2 секунды
            while attempt <= max_attempts:
                try:
                    payload = {
                        "organizationId": organization_id,
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

    async def send_telegram_message(self, text, chat_id=None):
        """Отправка сообщения в Telegram."""
        target_chat_id = chat_id or self.chat_id
        try:
            await self.bot.send_message(
                chat_id=target_chat_id,
                text=text
            )
            return True
        except TelegramError as e:
            print(f"Ошибка отправки сообщения в чат {target_chat_id}: {str(e)}")
            return False

    async def send_table_screenshot(self, chat_id=None):
        """Отправка скриншота таблицы в Telegram."""
        target_chat_id = chat_id or self.new_chat_id
        screenshot_path = None
        try:
            print("📸 Создаем скриншот таблицы...")
            screenshot_path = f"table_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            
            # Создаем скриншот
            success = await create_table_screenshot(screenshot_path)
            
            # Проверяем успешность создания И существование файла И его размер
            if success and os.path.exists(screenshot_path) and os.path.getsize(screenshot_path) > 0:
                # Отправляем фото
                with open(screenshot_path, 'rb') as photo:
                    await self.bot.send_photo(
                        chat_id=target_chat_id,
                        photo=photo
                    )
                
                # Удаляем временный файл
                os.remove(screenshot_path)
                print(f"✅ Скриншот таблицы отправлен в чат {target_chat_id}")
                return True
            else:
                print("❌ Не удалось создать скриншот таблицы")
                return False
                
        except Exception as e:
            error_msg = str(e)
            # Проверяем, является ли это ошибкой Playwright о отсутствующем браузере
            if "Executable doesn't exist" in error_msg and "playwright" in error_msg.lower():
                # Если это ошибка Playwright, но скриншот все равно был создан, не показываем ошибку
                if screenshot_path and os.path.exists(screenshot_path) and os.path.getsize(screenshot_path) > 0:
                    print("⚠️ Playwright предупреждение проигнорировано - скриншот создан успешно")
                    # Отправляем скриншот
                    with open(screenshot_path, 'rb') as photo:
                        await self.bot.send_photo(
                            chat_id=target_chat_id,
                            photo=photo
                        )
                    os.remove(screenshot_path)
                    print(f"✅ Скриншот таблицы отправлен в чат {target_chat_id}")
                    return True
                else:
                    print(f"❌ Ошибка Playwright: {error_msg}")
                    # НЕ отправляем ошибку Playwright в чат - только логируем
                    return False
            else:
                print(f"❌ Ошибка при отправке скриншота таблицы: {error_msg}")
                # НЕ отправляем ошибку в чат - только логируем
                return False
        finally:
            # Удаляем временный файл, если он был создан, но не отправлен
            if screenshot_path and os.path.exists(screenshot_path):
                try:
                    os.remove(screenshot_path)
                    print(f"🗑️ Удален временный файл: {screenshot_path}")
                except Exception as e:
                    print(f"⚠️ Не удалось удалить временный файл {screenshot_path}: {e}")

    async def run_report(self, update=None, target_chat_id=None, force_update_nomenclature=False):
        try:
            print("Начало формирования отчета...")
            
            # Получаем токен и организации
            token = await self.get_access_token()
            organizations = await self.get_organizations(token)
            
            # Находим организацию "Скандинавия" для получения номенклатуры
            scandinavia_org = None
            for org in organizations:
                if isinstance(org, dict) and "Скандинавия" in org.get("name", ""):
                    scandinavia_org = org
                    break
            
            if not scandinavia_org:
                raise Exception("Не найдена организация 'Скандинавия' для получения номенклатуры")
            
            print(f"Получаем полную номенклатуру из Колл центра")
            
            # Получаем номенклатуру по всем организациям (пустой список productIds - получим всю номенклатуру)
            nomenclature = await self.get_products_info(token, [], force_update=force_update_nomenclature)
            
            # Создаем словарь productId -> название блюда
            product_id_to_name = {}
            product_id_to_category = {}
            category_id_to_name = {}
            
            # Создаем словарь категорий
            for cat in nomenclature.get("productCategories", []):
                category_id_to_name[cat["id"]] = cat["name"].lower()
            
            # Создаем словари для продуктов
            for product in nomenclature.get("products", []):
                product_id = product["id"]
                product_name = product["name"]
                category_id = product.get("productCategoryId")
                category_name = category_id_to_name.get(category_id, "").lower()
                
                product_id_to_name[product_id] = product_name
                product_id_to_category[product_id] = category_name
            
            print(f"Загружено {len(product_id_to_name)} продуктов из номенклатуры")
            
            # Список исключений
            exclude_categories = [
                "десерты", "десерты понедельник", "десерты вторник", 
                "десерты среда", "десерты четверг", "пиво", "соусы"
            ]
            exclude_dishes = [
                "рис острый", "индиан тоник", "сырный соус", "хлебная корзинка", 
                "сырный heinz", "хлебная белая корзинка", "хлебная ч/б корзинка", 
                "хлебная черная корзинка"
            ]
            exclude_orgs = ["кожуховская", "рязань", "наметкина"]
            
            # Собираем отчеты по организациям
            org_reports = {}
            
            print("Получение стоп-листов по организациям...")
            for org in organizations:
                if not isinstance(org, dict):
                    continue
                    
                org_id = org.get("id")
                org_name = org.get("name")
                
                if not org_id or not org_name:
                    continue
                
                # Пропускаем исключенные организации
                if any(ex in org_name.lower() for ex in exclude_orgs):
                    print(f"Пропускаем организацию: {org_name}")
                    continue
                
                print(f"Обрабатываем организацию: {org_name}")
                
                # Получаем стоп-лист организации
                stop_list = await self.get_stop_list(token, org_id)
                
                org_products = []
                
                # Обрабатываем стоп-лист
                for group in stop_list.get("terminalGroupStopLists", []):
                    for terminal in group.get("items", []):
                        for item in terminal.get("items", []):
                            if not isinstance(item, dict):
                                continue
                            
                            # Включаем все товары из стоп-листа (независимо от остатка)
                            # balance может быть 0 (нет в наличии) или больше 0 (есть остаток)
                            
                            product_id = item.get("productId")
                            if not product_id:
                                continue
                            
                            # Получаем название блюда из номенклатуры
                            product_name = product_id_to_name.get(product_id)
                            if not product_name:
                                print(f"Не найдено название для productId: {product_id}")
                                continue
                            
                            # Получаем категорию блюда
                            category = product_id_to_category.get(product_id, "")
                            
                            # Пропускаем исключенные категории
                            if category in exclude_categories:
                                continue
                            
                            # Пропускаем исключенные блюда
                            if any(excluded_dish.lower() in product_name.lower() for excluded_dish in exclude_dishes):
                                continue
                            
                            # Пропускаем напитки, кроме морса
                            if category == "напитки" and "морс" not in product_name.lower():
                                continue
                            
                            org_products.append(product_name)
                
                # Добавляем в отчет, если есть товары в стоп-листе
                if org_products:
                    org_reports[org_name] = org_products
                    print(f"В организации {org_name} найдено {len(org_products)} товаров в стоп-листе")
                else:
                    print(f"В организации {org_name} нет товаров в стоп-листе")
            
            # Проверяем, есть ли данные для отчета
            if not org_reports:
                message = "Нет данных для отчета"
                if update:
                    await update.message.reply_text(message)
                else:
                    await self.send_telegram_message(message, target_chat_id)
                return
            
            print("Формирование и отправка отчета...")
            
            # Формируем текстовый отчет
            report_text = "📋 Отчет по стоп-листам:\n\n"
            
            # Сортируем организации по номеру
            sorted_orgs = sorted(org_reports.items(), key=lambda x: self.extract_org_number(x[0]))
            
            for org_name, products in sorted_orgs:
                # Извлекаем номер и название филиала
                org_number = self.extract_org_number(org_name)
                # Убираем номер из названия для отображения
                display_name = re.sub(r'^\d+\.\s*', '', org_name)
                
                report_text += f"🏪 {org_number}. {display_name}:\n"
                for product in sorted(products):
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
                        await self.send_telegram_message(part, target_chat_id)
            else:
                if update:
                    await update.message.reply_text(report_text)
                else:
                    await self.send_telegram_message(report_text, target_chat_id)
            
            print("Отчет успешно отправлен")
            
        except Exception as e:
            error_msg = f"Ошибка при формировании отчета: {str(e)}"
            print(error_msg)
            if update:
                await update.message.reply_text(error_msg)
            else:
                # НЕ отправляем ошибки в чат - только логируем
                pass

    async def close(self):
        """Закрытие соединений и остановка планировщика"""
        print("🔄 Закрытие соединений...")
        
        # Останавливаем планировщик только если он запущен
        if self.scheduler_running:
            print("🔄 Останавливаем планировщик...")
            try:
                await self.stop_scheduler()
            except Exception as e:
                print(f"⚠️ Ошибка при остановке планировщика: {e}")
        
        # Закрываем aiohttp сессию
        if self.aiohttp_session and not self.aiohttp_session.closed:
            try:
                await self.aiohttp_session.close()
                print("✅ aiohttp сессия закрыта")
            except Exception as e:
                print(f"⚠️ Ошибка при закрытии aiohttp сессии: {e}")
        
        print("✅ Все соединения закрыты")

async def report_command(update, context):
    await update.message.reply_text("Формирую отчет...")
    await context.bot_data['reporter'].run_report(update)

async def help_command(update, context):
    await update.message.reply_text(
        "/report — сформировать отчет\n"
        "/report_fresh — сформировать отчет с актуальной номенклатурой\n"
        "/schedule — показать запланированные задачи\n"
        "/restart_schedule — перезапустить планировщик\n"
        "/update_cache — принудительно обновить кеш номенклатуры\n"
        "/help — справка\n"
        "/ping — проверить, что бот работает\n\n"
        "📅 **Автоматическая отправка:**\n"
        "• Стоп-лист отправляется каждый час с 11:00 по 22:00 по МСК (основной чат)\n"
        "• Дополнительная отправка в новый чат в 12:00 и 17:00 по МСК\n"
        "• Кеш номенклатуры обновляется каждый день в 00:00 по МСК\n\n"
        "💡 **Примечание:**\n"
        "• /report использует кешированную номенклатуру (быстрее)\n"
        "• /report_fresh получает актуальную номенклатуру (медленнее, но полнее)"
    )

async def ping_command(update, context):
    await update.message.reply_text("Бот работает!")

async def schedule_command(update, context):
    """Проверка статуса планировщика"""
    reporter = context.bot_data['reporter']
    
    moscow_time = datetime.now(pytz.timezone('Europe/Moscow'))
    utc_time = datetime.now(pytz.UTC)
    
    schedule_text = f"📅 **Статус планировщика:**\n\n"
    schedule_text += f"🕐 Текущее время МСК: {moscow_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    schedule_text += f"🕐 Текущее время UTC: {utc_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    if reporter.scheduler_running:
        schedule_text += "✅ **Планировщик активен**\n\n"
        schedule_text += "📋 **Запланированные задачи:**\n"
        schedule_text += "• Отправка стоп-листа: каждый час с 11:00 по 22:00 МСК (основной чат)\n"
        schedule_text += "• Дополнительная отправка в новый чат: 12:00 и 17:00 МСК\n"
        schedule_text += "• Обновление кеша номенклатуры: каждый день в 00:00 МСК\n\n"
        
        # Показываем следующее время отправки
        current_hour = moscow_time.hour
        current_minute = moscow_time.minute
        
        # Определяем следующее время отправки в основной чат
        if 11 <= current_hour <= 22:
            if current_minute == 0:
                next_report_hour = current_hour + 1 if current_hour < 22 else 11
            else:
                next_report_hour = current_hour
            next_report_time = moscow_time.replace(hour=next_report_hour, minute=0, second=0, microsecond=0)
            if current_hour == 22 and current_minute == 0:
                next_report_time += timedelta(days=1)
            schedule_text += f"🕐 Следующий отчет (основной чат): {next_report_time.strftime('%d.%m.%Y %H:%M:%S')} МСК\n"
        else:
            next_report_time = moscow_time.replace(hour=11, minute=0, second=0, microsecond=0)
            if current_hour >= 23 or current_hour < 11:
                next_report_time += timedelta(days=1)
            schedule_text += f"🕐 Следующий отчет (основной чат): {next_report_time.strftime('%d.%m.%Y %H:%M:%S')} МСК\n"
        
        # Определяем следующее время отправки в новый чат
        if current_hour in [12, 17]:
            if current_minute == 0:
                next_new_chat_hour = 17 if current_hour == 12 else 12
                next_new_chat_time = moscow_time.replace(hour=next_new_chat_hour, minute=0, second=0, microsecond=0)
                if current_hour == 17:
                    next_new_chat_time += timedelta(days=1)
            else:
                next_new_chat_time = moscow_time.replace(hour=current_hour, minute=0, second=0, microsecond=0)
            schedule_text += f"🕐 Следующий отчет (новый чат): {next_new_chat_time.strftime('%d.%m.%Y %H:%M:%S')} МСК\n"
        elif current_hour < 12:
            next_new_chat_time = moscow_time.replace(hour=12, minute=0, second=0, microsecond=0)
            schedule_text += f"🕐 Следующий отчет (новый чат): {next_new_chat_time.strftime('%d.%m.%Y %H:%M:%S')} МСК\n"
        elif current_hour < 17:
            next_new_chat_time = moscow_time.replace(hour=17, minute=0, second=0, microsecond=0)
            schedule_text += f"🕐 Следующий отчет (новый чат): {next_new_chat_time.strftime('%d.%m.%Y %H:%M:%S')} МСК\n"
        else:
            next_new_chat_time = moscow_time.replace(hour=12, minute=0, second=0, microsecond=0) + timedelta(days=1)
            schedule_text += f"🕐 Следующий отчет (новый чат): {next_new_chat_time.strftime('%d.%m.%Y %H:%M:%S')} МСК\n"
    else:
        schedule_text += "❌ **Планировщик неактивен**\n\n"
        schedule_text += "Используйте /restart_schedule для запуска"
    
    await update.message.reply_text(schedule_text, parse_mode='Markdown')

async def restart_schedule_command(update, context):
    """Перезапуск планировщика"""
    reporter = context.bot_data['reporter']
    
    try:
        # Останавливаем планировщик
        if reporter.scheduler_running:
            await reporter.stop_scheduler()
        
        # Запускаем планировщик
        await reporter.start_scheduler()
        
        await update.message.reply_text("✅ Планировщик успешно перезапущен!")
        
        # Показываем обновленный статус
        await schedule_command(update, context)
        
    except Exception as e:
        error_msg = f"❌ Ошибка при перезапуске планировщика: {str(e)}"
        print(error_msg)
        await update.message.reply_text(error_msg)

async def update_cache_command(update, context):
    """Принудительное обновление кеша номенклатуры"""
    reporter = context.bot_data['reporter']
    
    try:
        await update.message.reply_text("🔄 Обновляю кеш номенклатуры...")
        
        # Принудительно обновляем кеш
        await reporter._update_nomenclature_cache()
        
        await update.message.reply_text("✅ Кеш номенклатуры успешно обновлен!")
        
    except Exception as e:
        error_msg = f"❌ Ошибка при обновлении кеша: {str(e)}"
        print(error_msg)
        await update.message.reply_text(error_msg)

async def report_fresh_command(update, context):
    """Формирование отчета с принудительным обновлением номенклатуры"""
    await update.message.reply_text("🔄 Формирую отчет с актуальной номенклатурой...")
    await context.bot_data['reporter'].run_report(update, force_update_nomenclature=True)

async def test_new_chat_command(update, context):
    """Тестовая отправка отчета в новый чат"""
    reporter = context.bot_data['reporter']
    try:
        await update.message.reply_text(f"🔄 Тестирую отправку в новый чат (ID: {reporter.new_chat_id})...")
        await reporter._send_scheduled_report_to_new_chat()
        await update.message.reply_text("✅ Тестовая отправка в новый чат завершена!")
    except Exception as e:
        error_msg = f"❌ Ошибка при тестовой отправке в новый чат: {str(e)}"
        print(error_msg)
        await update.message.reply_text(error_msg)

async def post_init(application):
    reporter = application.bot_data['reporter']
    print("🔄 Инициализация приложения...")
    
    # Проверяем кэш перед запуском планировщика
    print("📋 Проверяем состояние кэша номенклатуры...")
    if not reporter.is_nomenclature_cache_valid():
        print("🔄 Кэш номенклатуры устарел, обновляем...")
        try:
            await reporter._update_nomenclature_cache()
            print("✅ Кэш номенклатуры обновлен при инициализации")
        except Exception as e:
            print(f"❌ Ошибка при обновлении кэша при инициализации: {str(e)}")
    else:
        print("✅ Кэш номенклатуры актуален")
    
    # Запускаем планировщик как task
    scheduler_task = asyncio.create_task(reporter._scheduler_loop())
    reporter.scheduler_running = True
    print("✅ Планировщик запущен")

async def test_report():
    """Тестовая функция для диагностики отчета"""
    print("🧪 Тестирование отчета...")
    
    try:
        # Создаем экземпляр репортера
        reporter = IikoReporter()
        print("✅ Репортер создан")
        
        # Получаем токен
        print("🔑 Получаем токен...")
        token = await reporter.get_access_token()
        print(f"✅ Токен получен: {token[:20]}...")
        
        # Получаем организации
        print("🏢 Получаем организации...")
        organizations = await reporter.get_organizations(token)
        print(f"✅ Получено организаций: {len(organizations)}")
        
        # Выводим список организаций
        for i, org in enumerate(organizations[:5]):  # Показываем первые 5
            if isinstance(org, dict):
                print(f"  {i+1}. {org.get('name', 'N/A')} (ID: {org.get('id', 'N/A')})")
        
        # Проверяем кеш номенклатуры
        print("\n📋 Проверяем кеш номенклатуры...")
        if reporter.is_nomenclature_cache_valid():
            print("✅ Кеш номенклатуры актуален")
            cache_data = reporter.load_nomenclature_cache()
            if cache_data:
                print(f"✅ Загружено товаров в кеше: {len(cache_data)}")
            else:
                print("❌ Кеш пустой")
        else:
            print("❌ Кеш номенклатуры неактуален или отсутствует")
        
        # Тестируем получение стоп-листа для первой организации
        if organizations:
            first_org = organizations[0]
            if isinstance(first_org, dict):
                print(f"\n🛑 Тестируем стоп-лист для организации: {first_org.get('name', 'N/A')}")
                stop_list = await reporter.get_stop_list(token, first_org['id'])
                print(f"✅ Получено товаров в стоп-листе: {len(stop_list) if stop_list else 0}")
                print("Примеры товаров в стоп-листе:")
                count = 0
                for group in stop_list.get("terminalGroupStopLists", []):
                    for terminal in group.get("items", []):
                        for item in terminal.get("items", []):
                            if not isinstance(item, dict):
                                continue
                            print(f"  {count+1}. ProductId: {item.get('productId', 'N/A')}")
                            count += 1
                            if count >= 3:
                                break
                        if count >= 3:
                            break
                    if count >= 3:
                        break
        
        # Запускаем полный отчет
        print("\n📊 Запускаем полный отчет...")
        await reporter.run_report()
        print("✅ Отчет завершен")
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        if 'reporter' in locals():
            await reporter.close()

async def main_polling_async():
    """Асинхронная версия main_polling для проверки кэша"""
    reporter = IikoReporter()
    print("IIKO_API_KEY:", 'OK' if reporter.api_key else 'NOT SET')
    print("TELEGRAM_BOT_TOKEN:", 'OK' if reporter.telegram_token else 'NOT SET')
    print("TELEGRAM_CHAT_ID:", 'OK' if reporter.chat_id else 'NOT SET')
    if not all([reporter.api_key, reporter.telegram_token, reporter.chat_id]):
        print("Ошибка: Не все переменные окружения заданы. Проверьте .env файл или переменные окружения.")
        sys.exit(1)
    if not reporter.telegram_token or not reporter.telegram_token.startswith('5'):
        print("Внимание: Telegram токен выглядит некорректно. Проверьте его в .env!")
    
    # Проверяем кэш перед запуском приложения
    print("📋 Проверяем состояние кэша номенклатуры...")
    if not reporter.is_nomenclature_cache_valid():
        print("🔄 Кэш номенклатуры устарел, обновляем...")
        try:
            await reporter._update_nomenclature_cache()
            print("✅ Кэш номенклатуры обновлен при запуске")
        except Exception as e:
            print(f"❌ Ошибка при обновлении кэша при запуске: {str(e)}")
    else:
        print("✅ Кэш номенклатуры актуален")
    
    application = Application.builder().token(reporter.telegram_token).post_init(post_init).build()
    application.bot_data['reporter'] = reporter
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(CommandHandler("report_fresh", report_fresh_command))
    application.add_handler(CommandHandler("test_new_chat", test_new_chat_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ping", ping_command))
    application.add_handler(CommandHandler("schedule", schedule_command))
    application.add_handler(CommandHandler("restart_schedule", restart_schedule_command))
    application.add_handler(CommandHandler("update_cache", update_cache_command))
    print("Запуск polling...")
    
    # Обработчик сигналов для корректного завершения
    def signal_handler(signum, frame):
        print(f"\n🔄 Получен сигнал {signum}, завершаем работу...")
        asyncio.create_task(application.stop())
    
    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await application.run_polling()
    except KeyboardInterrupt:
        print("\n🔄 Получен сигнал прерывания, завершаем работу...")
    except Exception as e:
        print(f"Ошибка при запуске polling: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Polling завершён, закрытие сессии...")
        try:
            await reporter.close()
        except Exception as e:
            print(f"Ошибка при закрытии: {e}")

def main_polling():
    try:
        # Исправляем проблему с event loop
        import asyncio
        import nest_asyncio
        
        # Разрешаем вложенные event loops
        nest_asyncio.apply()
        
        # Проверяем, есть ли уже запущенный event loop
        try:
            loop = asyncio.get_running_loop()
            print("⚠️ Event loop уже запущен, используем существующий")
            # Создаем задачу в существующем loop
            loop.create_task(main_polling_async())
            loop.run_forever()
        except RuntimeError:
            # Нет запущенного loop, создаем новый
            asyncio.run(main_polling_async())
            
    except KeyboardInterrupt:
        print("\n🔄 Получен сигнал прерывания, завершаем работу...")
    except Exception as e:
        print(f"Ошибка при запуске: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    import sys
    import asyncio
    print('sys.argv:', sys.argv)
    # Проверяем аргументы командной строки
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("Запуск тестового режима...")
        asyncio.run(test_report())
    else:
        main_polling()