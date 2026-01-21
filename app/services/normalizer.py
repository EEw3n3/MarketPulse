import re
from typing import Optional

class VolumeNormalizer:
    """
    Standardizes product volumes from titles.
    Converts:
    - '50 ml', '50ml', '50ML', '0.05l' -> '50ml'
    - '100 g', '100gr' -> '100g'
    """
    
    # Pre-compiled regex for performance
    # Matches: number + optional space + unit (ml, l, g, kg, oz)
    # Group 1: Number
    # Group 2: Unit
    REGEX_VOLUME = re.compile(r'(\d+[.,]?\d*)\s*(ml|l|g|kg|gr|oz|мл|л|г)', re.IGNORECASE)

    @staticmethod
    def extract_volume(text: str) -> Optional[str]:
        """
        Extracts the first volume pattern found in the text and returns a standardized string.
        Returns None if no volume is found.
        """
        if not text:
            return None
            
        match = VolumeNormalizer.REGEX_VOLUME.search(text)
        if match:
            amount_str = match.group(1).replace(',', '.')
            unit = match.group(2).lower()
            
            try:
                amount = float(amount_str)
            except ValueError:
                return None

            # Standardization logic
            if unit in ['l', 'л']:
                # Convert Liters to Milliliters (0.1l -> 100ml)
                amount = amount * 1000
                unit = 'ml'
            elif unit in ['ml', 'ml.', 'мл']:
                unit = 'ml'
            elif unit in ['g', 'gr', 'г']:
                unit = 'g'
            elif unit in ['kg', 'кг']:
                # Convert Kg to Grams
                amount = amount * 1000
                unit = 'g'
            elif unit == 'oz':
                # Convert fl oz to ml (approx)
                amount = amount * 29.5735
                unit = 'ml'
                
            # Format: '50ml' (integer if no decimal needed)
            if amount.is_integer():
                return f"{int(amount)}{unit}"
            else:
                return f"{round(amount, 1)}{unit}"
                
        return None

    @staticmethod
    def normalize_title(title: str) -> str:
        """
        Returns a title with localized units standardized.
        (e.g., "Chanel 0.05l" -> "Chanel 50ml")
        """
        volume = VolumeNormalizer.extract_volume(title)
        if volume:
            # We could replace the original volume in the string, 
            # but for now, just appending or ensuring it's known is enough.
            # This method acts as a helper to verify we CAN normalize it.
            return f"{title} [{volume}]"
        return title

volume_normalizer = VolumeNormalizer()
