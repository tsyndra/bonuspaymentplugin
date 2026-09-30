import os
import sys
import asyncio
import signal
from datetime import datetime, timedelta

import pytz
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler

from table_screenshot import create_table_screenshot

# Screenshot slots (MSK): hour -> minutes
SCREENSHOT_SLOTS = {
    12: (0,),
    17: (0,),
    18: (0,),
    19: (0,),
    20: (0,),
    21: (0, 30),
    22: (0,),
}


class IikoReporter:
    def __init__(self):
        load_dotenv()
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.new_chat_id = os.getenv("TELEGRAM_NEW_CHAT_ID", "-1001507942384")

        if not self.telegram_token:
            raise ValueError("Не задан TELEGRAM_BOT_TOKEN")
        if not (self.new_chat_id or self.chat_id):
            raise ValueError("Не задан TELEGRAM_NEW_CHAT_ID или TELEGRAM_CHAT_ID")

        print(f"Основной чат ID: {self.chat_id}")
        print(f"Чат для скриншотов ID: {self.new_chat_id}")

        self.bot = Bot(token=self.telegram_token)
        self.scheduler_running = False
        self.scheduler_task = None

    async def start_scheduler(self):
        if self.scheduler_running and self.scheduler_task and not self.scheduler_task.done():
            return self.scheduler_task

        self.scheduler_running = True
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        print("Планировщик запущен")
        return self.scheduler_task

    async def stop_scheduler(self):
        if not self.scheduler_running:
            return
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
        print(
            "📸 Отправка скриншотов таблицы в "
            "12:00, 17:00, 18:00, 19:00, 20:00, 21:00, 21:30, 22:00 по МСК"
        )

        msk_tz = pytz.timezone("Europe/Moscow")
        screenshot_marker_path = os.path.join(os.getcwd(), "last_screenshot_minute.txt")

        def _was_screenshot_sent_this_minute(now_dt):
            try:
                if not os.path.exists(screenshot_marker_path):
                    return False
                with open(screenshot_marker_path, "r", encoding="utf-8") as f:
                    return f.read().strip() == now_dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                return False

        def _mark_screenshot_sent(now_dt):
            try:
                with open(screenshot_marker_path, "w", encoding="utf-8") as f:
                    f.write(now_dt.strftime("%Y-%m-%d %H:%M"))
            except Exception:
                pass

        while self.scheduler_running:
            try:
                now = datetime.now(msk_tz)
                minutes = SCREENSHOT_SLOTS.get(now.hour)
                should_send = minutes is not None and now.minute in minutes

                if should_send:
                    if _was_screenshot_sent_this_minute(now):
                        print(
                            f"⏭️ Скриншот уже был отправлен в {now.strftime('%Y-%m-%d %H:%M')} — пропуск"
                        )
                    else:
                        print(f"📸 Отправляем скриншот таблицы в {now.strftime('%Y-%m-%d %H:%M:%S')} МСК")
                        if await self.send_table_screenshot():
                            _mark_screenshot_sent(now)

                now = datetime.now(msk_tz)
                next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
                sleep_seconds = (next_minute - now).total_seconds()
                if sleep_seconds > 0:
                    print(
                        f"🕐 Планировщик ждет {sleep_seconds:.1f} секунд "
                        f"до следующей проверки ({next_minute.strftime('%H:%M:%S')} МСК)..."
                    )
                    await asyncio.sleep(sleep_seconds)
                else:
                    await asyncio.sleep(1)

            except asyncio.CancelledError:
                print("Планировщик остановлен")
                break
            except Exception as e:
                print(f"❌ Ошибка в планировщике: {e}")
                await asyncio.sleep(60)

    async def send_table_screenshot(self, chat_id=None):
        """Отправка скриншота таблицы callcenter в Telegram."""
        target_chat_id = chat_id or self.new_chat_id or self.chat_id
        screenshot_path = None
        try:
            print("📸 Создаем скриншот таблицы...")
            screenshot_path = f"table_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

            success = await create_table_screenshot(screenshot_path)

            if success and os.path.exists(screenshot_path) and os.path.getsize(screenshot_path) > 0:
                with open(screenshot_path, "rb") as photo:
                    await self.bot.send_photo(chat_id=target_chat_id, photo=photo)
                os.remove(screenshot_path)
                print(f"✅ Скриншот таблицы отправлен в чат {target_chat_id}")
                return True

            print("❌ Не удалось создать скриншот таблицы")
            return False

        except Exception as e:
            error_msg = str(e)
            if "Executable doesn't exist" in error_msg and "playwright" in error_msg.lower():
                if screenshot_path and os.path.exists(screenshot_path) and os.path.getsize(screenshot_path) > 0:
                    print("⚠️ Playwright предупреждение проигнорировано - скриншот создан успешно")
                    with open(screenshot_path, "rb") as photo:
                        await self.bot.send_photo(chat_id=target_chat_id, photo=photo)
                    os.remove(screenshot_path)
                    print(f"✅ Скриншот таблицы отправлен в чат {target_chat_id}")
                    return True
                print(f"❌ Ошибка Playwright: {error_msg}")
                return False

            print(f"❌ Ошибка при отправке скриншота таблицы: {error_msg}")
            return False
        finally:
            if screenshot_path and os.path.exists(screenshot_path):
                try:
                    os.remove(screenshot_path)
                    print(f"🗑️ Удален временный файл: {screenshot_path}")
                except Exception as e:
                    print(f"⚠️ Не удалось удалить временный файл {screenshot_path}: {e}")

    async def close(self):
        print("🔄 Закрытие соединений...")
        if self.scheduler_running:
            try:
                await self.stop_scheduler()
            except Exception as e:
                print(f"⚠️ Ошибка при остановке планировщика: {e}")
        print("✅ Все соединения закрыты")


async def help_command(update, context):
    await update.message.reply_text(
        "/screenshot — отправить скриншот таблицы ХВ сейчас\n"
        "/schedule — показать расписание\n"
        "/restart_schedule — перезапустить планировщик\n"
        "/ping — проверка бота\n"
        "/help — эта справка\n\n"
        "Скриншоты автоматически: 12:00, 17:00, 18:00, 19:00, 20:00, 21:00, 21:30, 22:00 МСК"
    )


async def ping_command(update, context):
    await update.message.reply_text("pong")


async def screenshot_command(update, context):
    await update.message.reply_text("📸 Делаю скриншот таблицы...")
    ok = await context.bot_data["reporter"].send_table_screenshot()
    if ok:
        await update.message.reply_text("✅ Скриншот отправлен")
    else:
        await update.message.reply_text("❌ Не удалось сделать скриншот — смотри логи")


async def schedule_command(update, context):
    reporter = context.bot_data["reporter"]
    msk_tz = pytz.timezone("Europe/Moscow")
    moscow_time = datetime.now(msk_tz)

    lines = [
        "📅 Статус планировщика:\n",
        f"🕐 Сейчас МСК: {moscow_time.strftime('%Y-%m-%d %H:%M:%S')}\n",
    ]

    if reporter.scheduler_running:
        lines.append("✅ Планировщик активен\n")
        lines.append(
            "📸 Слоты: 12:00, 17:00, 18:00, 19:00, 20:00, 21:00, 21:30, 22:00 МСК\n"
        )

        slots = []
        for hour in sorted(SCREENSHOT_SLOTS):
            for minute in SCREENSHOT_SLOTS[hour]:
                slots.append((hour, minute))

        next_time = None
        for hour, minute in slots:
            candidate = moscow_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate > moscow_time:
                next_time = candidate
                break
        if next_time is None:
            hour, minute = slots[0]
            next_time = (moscow_time + timedelta(days=1)).replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
        lines.append(f"🕐 Следующий скриншот: {next_time.strftime('%d.%m.%Y %H:%M:%S')} МСК")
    else:
        lines.append("❌ Планировщик неактивен\n")
        lines.append("Используйте /restart_schedule для запуска")

    await update.message.reply_text("".join(lines))


async def restart_schedule_command(update, context):
    reporter = context.bot_data["reporter"]
    try:
        await update.message.reply_text("🔄 Перезапускаю планировщик...")
        if reporter.scheduler_running:
            await reporter.stop_scheduler()
        await reporter.start_scheduler()
        await update.message.reply_text("✅ Планировщик перезапущен")
        await schedule_command(update, context)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def post_init(application):
    reporter = application.bot_data["reporter"]
    print("🔄 Инициализация приложения...")
    await reporter.start_scheduler()
    print("✅ Планировщик запущен")


async def main_polling_async():
    reporter = IikoReporter()
    print("TELEGRAM_BOT_TOKEN:", "OK" if reporter.telegram_token else "NOT SET")
    print("TELEGRAM_NEW_CHAT_ID:", reporter.new_chat_id or "NOT SET")

    application = Application.builder().token(reporter.telegram_token).post_init(post_init).build()
    application.bot_data["reporter"] = reporter
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("start", help_command))
    application.add_handler(CommandHandler("ping", ping_command))
    application.add_handler(CommandHandler("screenshot", screenshot_command))
    application.add_handler(CommandHandler("schedule", schedule_command))
    application.add_handler(CommandHandler("restart_schedule", restart_schedule_command))
    print("Запуск polling...")

    def signal_handler(signum, frame):
        print(f"\n🔄 Получен сигнал {signum}, завершаем работу...")
        asyncio.create_task(application.stop())

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
        import nest_asyncio

        nest_asyncio.apply()
        try:
            loop = asyncio.get_running_loop()
            print("⚠️ Event loop уже запущен, используем существующий")
            loop.create_task(main_polling_async())
            loop.run_forever()
        except RuntimeError:
            asyncio.run(main_polling_async())
    except KeyboardInterrupt:
        print("\n🔄 Получен сигнал прерывания, завершаем работу...")
    except Exception as e:
        print(f"Ошибка при запуске: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    load_dotenv()
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("Запуск тестового скриншота...")

        async def _test():
            reporter = IikoReporter()
            try:
                ok = await reporter.send_table_screenshot()
                print("✅ OK" if ok else "❌ FAIL")
            finally:
                await reporter.close()

        asyncio.run(_test())
    else:
        main_polling()
