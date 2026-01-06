import asyncio
import random
from playwright.async_api import Page
from loguru import logger

class Humanizer:
    """
    Эмулирует поведение человека: нелинейные движения мыши,
    случайные паузы, "человеческий" скролл.
    """

    @staticmethod
    async def human_scroll(page: Page):
        """
        Скроллит страницу вниз рывками, имитируя чтение/просмотр.
        """
        try:
            # Получаем высоту страницы
            total_height = await page.evaluate("document.body.scrollHeight")
            # viewport_size - это свойство, а не асинхронный метод
            viewport = page.viewport_size
            viewport_height = viewport['height'] if viewport else 1080
            
            current_scroll = 0
            
            # Скроллим не до самого конца, а случайно (человек редко доходит до пикселя)
            limit = total_height * random.uniform(0.7, 0.9)

            while current_scroll < limit:
                # Случайный шаг скролла
                scroll_step = random.randint(300, 700)
                current_scroll += scroll_step
                
                # Плавно скроллим
                await page.mouse.wheel(0, scroll_step)
                
                # Случайная пауза "на чтение"
                await asyncio.sleep(random.uniform(0.2, 1.2))
                
                # Иногда двигаем мышкой "просто так"
                if random.random() < 0.3:
                    await Humanizer.random_mouse_move(page)

        except Exception as e:
            logger.warning(f"Ошибка human_scroll: {e}")

    @staticmethod
    async def random_mouse_move(page: Page):
        """
        Двигает курсор в случайную точку на экране.
        """
        try:
            # ИСПРАВЛЕНИЕ ЗДЕСЬ: viewport_size - это свойство, скобки не нужны
            viewport = page.viewport_size
            if not viewport:
                viewport = {"width": 1920, "height": 1080}

            end_x = random.randint(0, viewport['width'])
            end_y = random.randint(0, viewport['height'])

            # Рисуем кривую (шаги)
            steps = random.randint(10, 25)
            await page.mouse.move(end_x, end_y, steps=steps)
            
        except Exception as e:
            logger.warning(f"Ошибка human_mouse: {e}")

    @staticmethod
    async def smart_wait(min_s=1.0, max_s=3.0):
        """Умная пауза"""
        await asyncio.sleep(random.uniform(min_s, max_s))