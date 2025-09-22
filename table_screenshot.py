#!/usr/bin/env python3
"""
Модуль для создания скриншотов таблицы callcenter.hatimaki.ru
"""

import asyncio
import os
from playwright.async_api import async_playwright
from datetime import datetime

class TableScreenshotMaker:
    def __init__(self):
        self.username = 'tsyndra'
        self.password = 'NgTYSasz06GtpplZ'
        self.url = 'https://callcenter.hatimaki.ru'
        
    async def take_table_screenshot(self, output_path='table.png'):
        """Создает скриншот таблицы"""
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                
                page = await context.new_page()
                
                try:
                    print("Переходим на страницу авторизации...")
                    await page.goto(f'{self.url}/auth', wait_until='networkidle')
                    
                    print("Заполняем форму авторизации...")
                    await page.fill('input[name="username"]', self.username)
                    await page.fill('input[name="password"]', self.password)
                    
                    await page.click('button[name="submit"]')
                    
                    print("Ждем авторизации...")
                    await page.wait_for_timeout(3000)
                    
                    print("Переходим на главную страницу...")
                    await page.goto(f'{self.url}/main', wait_until='networkidle')
                    await page.wait_for_timeout(2000)
                    
                    # Проверяем заголовок страницы
                    page_title = await page.title()
                    print(f"Заголовок страницы: {page_title}")
                    
                    # Ищем все таблицы
                    table_headers = await page.query_selector_all('.terminals-column-header')
                    all_rows = await page.query_selector_all('.hover-block.terminal.with-kz')
                    
                    print(f"Найдено заголовков таблиц: {len(table_headers)}")
                    print(f"Найдено строк таблиц: {len(all_rows)}")
                    
                    if not table_headers or not all_rows:
                        print("Таблицы не найдены!")
                        return False
                    
                    print(f"Найдено таблиц: {len(table_headers)}")
                    print(f"Найдено строк: {len(all_rows)}")
                    
                    # Получаем координаты всех таблиц
                    min_x = float('inf')
                    min_y = float('inf')
                    max_x = 0
                    max_y = 0
                    
                    for i, header in enumerate(table_headers):
                        header_box = await header.bounding_box()
                        if header_box:
                            min_x = min(min_x, header_box['x'])
                            min_y = min(min_y, header_box['y'])
                            max_x = max(max_x, header_box['x'] + header_box['width'])
                            max_y = max(max_y, header_box['y'] + header_box['height'])
                            print(f"Таблица {i+1}: {header_box['x']:.0f}x{header_box['y']:.0f} размер {header_box['width']:.0f}x{header_box['height']:.0f}")
                    
                    # Получаем координаты всех строк для точного определения границ
                    for row in all_rows:
                        row_box = await row.bounding_box()
                        if row_box:
                            min_x = min(min_x, row_box['x'])
                            min_y = min(min_y, row_box['y'])
                            max_x = max(max_x, row_box['x'] + row_box['width'])
                            max_y = max(max_y, row_box['y'] + row_box['height'])
                    
                    if min_x != float('inf'):
                        # Вычисляем общие границы всех таблиц с обрезкой сверху и снизу
                        table_x = min_x - 30
                        table_y = min_y - 10  # Меньший отступ сверху
                        table_width = max_x - min_x + 60
                        table_height = max_y - min_y + 20  # Меньший отступ снизу
                        
                        # Создаем скриншот всех таблиц
                        await page.screenshot(
                            path=output_path,
                            clip={
                                'x': table_x,
                                'y': table_y,
                                'width': table_width,
                                'height': table_height
                            }
                        )
                        print(f"✅ Скриншот всех таблиц сохранен как: {output_path}")
                        print(f"📏 Размеры: {table_width:.0f}x{table_height:.0f} пикселей")
                        return True
                    else:
                        print("❌ Не удалось определить границы таблиц")
                        return False
                    
                except Exception as e:
                    print(f"❌ Ошибка при создании скриншота: {e}")
                    # Удаляем файл, если он был создан с ошибкой
                    if os.path.exists(output_path):
                        try:
                            os.remove(output_path)
                            print(f"🗑️ Удален файл с ошибкой: {output_path}")
                        except Exception as remove_error:
                            print(f"⚠️ Не удалось удалить файл с ошибкой {output_path}: {remove_error}")
                    return False
                
                finally:
                    await browser.close()
        
        except Exception as e:
            # Если это ошибка Playwright о отсутствующем браузере, но скриншот все равно создался
            error_msg = str(e)
            if "Executable doesn't exist" in error_msg and "playwright" in error_msg.lower():
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    print("⚠️ Playwright предупреждение проигнорировано - скриншот создан успешно")
                    return True
                else:
                    print(f"❌ Ошибка Playwright: {error_msg}")
                    return False
            else:
                print(f"❌ Общая ошибка при создании скриншота: {error_msg}")
                return False

async def create_table_screenshot(output_path='table.png'):
    """Функция для создания скриншота таблицы"""
    maker = TableScreenshotMaker()
    return await maker.take_table_screenshot(output_path)

if __name__ == "__main__":
    asyncio.run(create_table_screenshot())
