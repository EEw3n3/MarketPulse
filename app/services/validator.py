from loguru import logger
from typing import List
from app.services.scraper import ScrapedItem

class ContentValidator:
    def __init__(self):
        # Basic "garbage" words for electronics
        self.accessory_markers = [
            # Exact word matches (require spaces around)
            "case", "cover", "holster", "korpus", "apvalks", "macins", "futrolis",
            "box", "dummy", "replacement", "part", "auduma", "silikona", "adas",
            # Substring matches (search everywhere)
            "protect", "shield", "guard", "armor", "film", "folija", "plēve", "pleve",
            "glass", "stikls", "screen", "ekran", "display",
            "cable", "kabel", "vads", "cord", "wire",
            "adapter", "charger", "lādē", "ladet", "power", "baterij", "battery",
            "strap", "band", "siksna", "belt",
            "mount", "holder", "stand", "turēt", "statīv",
            "cleaning", "tīrī", "repair", "remont",
            "magclick", "magnetic", "magsafe",
            "liquid", "hybrid", "combat", "optix", "fender" # Case model names often appearing without "case"
        ]

    def is_garbage(self, title: str, forbidden_keywords: List[str] = None) -> bool:
        """
        Keyword check
        """
        title_lower = title.lower()
        
        # First check user negative keywords from AI
        if forbidden_keywords:
            for word in forbidden_keywords:
                if word.lower() in title_lower:
                    return True
                    
        # Check extended marker list
        for marker in self.accessory_markers:
            # For short words (3-4 letters) better to use word boundaries
            if len(marker) < 4:
                 if f" {marker} " in f" {title_lower} ":
                     return True
            else:
                # For long words and specific terms - search substring
                # This will catch "NeoGlass", "Protector", "Charging"
                if marker in title_lower:
                    return True
        
        return False

    def check_brand(self, title: str, brand: str) -> bool:
        """
        Checks if brand matches (if specified)
        """
        if not brand:
            return True
            
        # If looking for Apple but title has Nike - it's garbage
        # But if looking for iPhone, "Apple" might not be in title
        # So flexibility is needed here
        title_lower = title.lower()
        brand_lower = brand.lower()
        
        # If title has another famous brand from blacklist - it's garbage
        # (e.g., searching for Apple, found Samsung)
        major_brands = ["apple", "samsung", "nike", "adidas", "sony", "lg"]
        if brand_lower in major_brands:
            other_brands = [b for b in major_brands if b != brand_lower]
            for other in other_brands:
                if other in title_lower:
                    logger.warning(f"🚫 Brand conflict: {title} (searching for {brand})")
                    return False
        
        return True

    def validate_items(self, items: List[ScrapedItem], intent: dict) -> List[ScrapedItem]:
        """
        Filters item list
        """
        brand = intent.get("brand")
        forbidden = intent.get("forbidden_keywords", [])
        
        valid_items = []
        for item in items:
            # 1. Check for accessories
            if self.is_garbage(item.title, forbidden):
                logger.debug(f"🗑️ Filtered accessory: {item.title}")
                continue
                
            # 2. Check brand match
            if not self.check_brand(item.title, brand):
                continue
                
            valid_items.append(item)
            
        logger.info(f"✅ Filtering finished: {len(valid_items)} out of {len(items)} items passed check.")
        return valid_items

content_validator = ContentValidator()
