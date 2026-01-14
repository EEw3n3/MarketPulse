import asyncio
import random
from playwright.async_api import Page
from loguru import logger

class Humanizer:
    """
    Emulates human behavior: non-linear mouse movements,
    random pauses, "human" scroll.
    """

    @staticmethod
    async def human_scroll(page: Page):
        """
        Scrolls the page down in jerks, simulating reading/viewing.
        """
        try:
            # Get page height
            total_height = await page.evaluate("document.body.scrollHeight")
            # viewport_size is a property, not an async method
            viewport = page.viewport_size
            viewport_height = viewport['height'] if viewport else 1080
            
            current_scroll = 0
            
            # Scroll not to the very end, but randomly (humans rarely reach the exact pixel)
            limit = total_height * random.uniform(0.7, 0.9)

            while current_scroll < limit:
                 # Random scroll step
                scroll_step = random.randint(300, 700)
                current_scroll += scroll_step
                
                # Smoothly scroll
                await page.mouse.wheel(0, scroll_step)
                
                # Random pause "for reading"
                await asyncio.sleep(random.uniform(0.2, 1.2))
                
                # Sometimes move the mouse "just because"
                if random.random() < 0.3:
                    await Humanizer.random_mouse_move(page)

        except Exception as e:
            logger.warning(f"human_scroll error: {e}")

    @staticmethod
    async def random_mouse_move(page: Page):
        """
        Moves the cursor to a random point on the screen.
        """
        try:
            # FIX HERE: viewport_size is a property, brackets are not needed
            viewport = page.viewport_size
            if not viewport:
                viewport = {"width": 1920, "height": 1080}

            end_x = random.randint(0, viewport['width'])
            end_y = random.randint(0, viewport['height'])

            # Draw a curve (steps)
            steps = random.randint(10, 25)
            await page.mouse.move(end_x, end_y, steps=steps)
            
        except Exception as e:
            logger.warning(f"human_mouse error: {e}")

    @staticmethod
    async def smart_wait(min_s=1.0, max_s=3.0):
        """Smart pause"""
        await asyncio.sleep(random.uniform(min_s, max_s))