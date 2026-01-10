from loguru import logger
from typing import List
from app.services.scraper import ScrapedItem

class ContentValidator:
    def __init__(self):
        # Базовые "мусорные" слова для электроники
        self.accessory_markers = [
            "case", "cover", "glass", "cable", "strap", "holster", 
            "чехол", "стекло", "кабель", "ремешок", "пленка", "защита",
            "adapter", "charger", "power bank", "box", "dummy"
        ]

    def is_garbage(self, title: str, forbidden_keywords: List[str] = None) -> bool:
        """
        Простая и быстрая проверка на ключевые слова
        """
        title_lower = title.lower()
        
        # Сначала проверяем пользовательские минус-слова от ИИ
        if forbidden_keywords:
            for word in forbidden_keywords:
                if word.lower() in title_lower:
                    return True
                    
        # Затем наши базовые маркеры
        for marker in self.accessory_markers:
            # Важно: ищем как отдельное слово или в составе, 
            # но с осторожностью (чтобы не убить "CaseLogic" если это бренд)
            if f" {marker} " in f" {title_lower} ":
                return True
        
        return False

    def check_brand(self, title: str, brand: str) -> bool:
        """
        Проверяет, совпадает ли бренд (если он указан)
        """
        if not brand:
            return True
            
        # Если мы ищем Apple, а в названии Nike - это мусор
        # Но если мы ищем iPhone, то "Apple" может и не быть в названии
        # Поэтому тут нужна гибкость
        title_lower = title.lower()
        brand_lower = brand.lower()
        
        # Если в названии есть другой известный бренд из черного списка - это мусор
        # (Например, ищем Apple, нашли Samsung)
        major_brands = ["apple", "samsung", "nike", "adidas", "sony", "lg"]
        if brand_lower in major_brands:
            other_brands = [b for b in major_brands if b != brand_lower]
            for other in other_brands:
                if other in title_lower:
                    logger.warning(f"🚫 Бренд-конфликт: {title} (ищем {brand})")
                    return False
        
        return True

    def validate_items(self, items: List[ScrapedItem], intent: dict) -> List[ScrapedItem]:
        """
        Фильтрует список товаров
        """
        brand = intent.get("brand")
        forbidden = intent.get("forbidden_keywords", [])
        
        valid_items = []
        for item in items:
            # 1. Проверка на аксессуары
            if self.is_garbage(item.title, forbidden):
                logger.debug(f"🗑️ Отфильтрован аксессуар: {item.title}")
                continue
                
            # 2. Проверка соответствия бренда
            if not self.check_brand(item.title, brand):
                continue
                
            valid_items.append(item)
            
        logger.info(f"✅ Фильтрация завершена: {len(valid_items)} из {len(items)} товаров прошли проверку.")
        return valid_items

content_validator = ContentValidator()
