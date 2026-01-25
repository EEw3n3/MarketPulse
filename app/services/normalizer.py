import re
from typing import Optional, Dict

class PerfumeNormalizer:
    """
    Advanced normalizer for perfume products.
    Extracts Brand, Volume, Concentration and removes noise like 'Vapo'.
    """
    
    # 1. Brands (Top common, can be expanded)
    BRANDS = [
        "Dior", "Chanel", "Armani", "Versace", "Gucci", "Prada", "Hermes", "Guerlain",
        "Dolce & Gabbana", "D&G", "Tom Ford", "Hugo Boss", "Boss", "Calvin Klein", "CK",
        "Yves Saint Laurent", "YSL", "Paco Rabanne", "Givency", "Valentino", "Bvlgari",
        "Lacoste", "Creed", "Montblanc", "Carolina Herrera", "Jean Paul Gaultier", "JPG"
    ]

    # 2. Concentrations
    CONC_MAP = {
        "edp": "EDP",
        "eau de parfum": "EDP",
        "parfīmērijas ūdens": "EDP",
        "edt": "EDT",
        "eau de toilette": "EDT",
        "tualetes ūdens": "EDT",
        "parfum": "Parfum",
        "pure parfum": "Parfum",
        "smaržas": "Parfum",
        "edc": "EDC",
        "eau de cologne": "EDC",
        "odekolons": "EDC"
    }

    # 3. Noise to ignore
    NOISE = [
        r"\bvapo\b", r"\bvaporisateur\b", r"\bspray\b", r"\bnatural spray\b",
        r"\bvīriešiem\b", r"\bmen\b", r"\bhomme\b", r"\bfor men\b"
    ]

    REGEX_VOLUME = re.compile(r'(\d+[.,]?\d*)\s*(ml|l|oz|мл|л)', re.IGNORECASE)

    @staticmethod
    def extract_all(title: str) -> Dict[str, Optional[str]]:
        """
        Extracts all attributes from the title.
        """
        title_lower = title.lower()
        
        # 1. Volume
        volume = PerfumeNormalizer.extract_volume(title)
        
        # 2. Brand
        brand = None
        for b in PerfumeNormalizer.BRANDS:
            if b.lower() in title_lower:
                brand = b
                break
        
        # 3. Concentration
        concentration = None
        for key, value in PerfumeNormalizer.CONC_MAP.items():
            if key in title_lower:
                concentration = value
                break
        
        # 4. Clean Name (remove volume, brand, concentration and noise)
        clean_name = title
        # Remove volume
        clean_name = PerfumeNormalizer.REGEX_VOLUME.sub("", clean_name)
        # Remove noise
        for n in PerfumeNormalizer.NOISE:
            clean_name = re.sub(n, "", clean_name, flags=re.IGNORECASE)
        
        # Final cleanup
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
        # Remove trailing dashes or commas
        clean_name = re.sub(r'^[,\-\s]+|[,\-\s]+$', '', clean_name)

        return {
            "brand": brand,
            "volume": volume,
            "concentration": concentration,
            "clean_name": clean_name
        }

    @staticmethod
    def extract_volume(text: str) -> Optional[str]:
        if not text: return None
        match = PerfumeNormalizer.REGEX_VOLUME.search(text)
        if match:
            amount_str = match.group(1).replace(',', '.')
            unit = match.group(2).lower()
            try:
                amount = float(amount_str)
                if unit in ['l', 'л']: amount *= 1000; unit = 'ml'
                elif unit in ['ml', 'мл']: unit = 'ml'
                elif unit == 'oz': amount *= 29.57; unit = 'ml'
                
                if amount.is_integer(): return f"{int(amount)}ml"
                return f"{round(amount, 1)}ml"
            except: return None
        return None

perfume_normalizer = PerfumeNormalizer()
