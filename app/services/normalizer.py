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
        "Yves Saint Laurent", "YSL", "Paco Rabanne", "Rabanne", "Givenchy", "Valentino", "Bvlgari",
        "Lacoste", "Creed", "Montblanc", "Carolina Herrera", "Jean Paul Gaultier", "JPG",
        "Jimmy Choo", "Police", "Azzaro", "Kenzo", "Lalique", "Issey Miyake", "Narciso Rodriguez",
        "Marlies Moller", "Shiseido", "Elizabeth Arden", "David Beckham", "Jaguar", "Rochas",
        "Tiziana Terenzi", "Lattafa", "Armaf", "Dsquared2", "Nasomatto", "V Canto", "Amouage", 
        "Mancera", "Montale", "Byredo", "Xerjoff", "Initio", "Roja", "Maison Francis Kurkdjian", "MFK",
        "Diptyque", "Rasasi", "Afnan", "Al Haramain", "Escentric Molecules", "Juliette Has A Gun",
        "Kilian", "Memo Paris", "Penhaligon's", "Vilhelm Parfumerie", "Acca Kappa", "Gritti",
        "Armand Basi", "Karl Lagerfeld", "Lagerfeld", "Zarkoperfume", "Maison Margiela", "Replica",
        "Acqua Di Parma", "Moschino", "Mont Blanc", "Bvlgari", "Chopard", "Jo Malone", "Le Labo",
        "By Kilian", "Bond No. 9", "Serge Lutens", "Frederic Malle", "Kilian Paris",
        "Trussardi", "Salvatore Ferragamo", "Ferragamo", "Rue Broca", "Monotheme", "Kajal", "Genyum", "Acorelle",
        "Elizabeth Arden", "Estee Lauder", "Clinique", "Biotherm", "Viktor & Rolf", "V&R", "Diesel", "Cacharel",
        "Maison Alhambra", "Rasasi", "Afnan", "Al Haramain", "Swiss Arabian", "Paris Corner", "Fragrance World",
        "Zadig & Voltaire", "Z&V", "Etro", "Missoni", "Baldessarini", "Joop!", "Nikolas de Barry"
    ]

    # Dynamic brands found during session
    DISCOVERED_BRANDS = set()

    # 2. Concentrations (Standardized)
    CONC_MAP = {
        "edp": "EDP",
        "eau de parfum": "EDP",
        "eau de parfum intense": "EDP",
        "parfimērijas ūdens": "EDP",
        "smaržūdens": "EDP",
        "edt": "EDT",
        "eau de toilette": "EDT",
        "tualetes ūdens": "EDT",
        "parfum": "Parfum",
        "pure parfum": "Parfum",
        "extrait de parfum": "Parfum",
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
        
        # 2. Brand (Strict Word Boundary Match, Longest first)
        brand = None
        # Combine static list with discovered brands
        all_known_brands = list(set(PerfumeNormalizer.BRANDS) | PerfumeNormalizer.DISCOVERED_BRANDS)
        sorted_brands = sorted(all_known_brands, key=len, reverse=True)
        
        for b in sorted_brands:
            pattern = rf'\b{re.escape(b.lower())}\b'
            if re.search(pattern, title_lower):
                brand = b
                break
        
        if not brand:
            # If no brand found, try taking the first one/two words
            words = title.split()
            if words:
                first_word = words[0].strip(",.- ")
                if first_word.lower() not in PerfumeNormalizer.CONC_MAP and \
                   not any(re.search(rf'\b{re.escape(first_word.lower())}\b', n) for n in PerfumeNormalizer.NOISE):
                    
                    brand = first_word
                    # Heuristic: if first word is short and there is a second word, combine them
                    if len(first_word) <= 3 and len(words) > 1:
                        brand = f"{first_word} {words[1].strip(',.- ')}"
        
        # 4. Concentration
        concentration = None
        sorted_conc_keys = sorted(PerfumeNormalizer.CONC_MAP.keys(), key=len, reverse=True)
        for key in sorted_conc_keys:
            pattern = rf'\b{re.escape(key)}\b'
            if re.search(pattern, title_lower):
                concentration = PerfumeNormalizer.CONC_MAP[key]
                break
        
        # 5. Clean Name
        clean_name = title
        clean_name = PerfumeNormalizer.REGEX_VOLUME.sub("", clean_name)
        for n in PerfumeNormalizer.NOISE:
            clean_name = re.sub(n, "", clean_name, flags=re.IGNORECASE)
        
        if brand: 
            clean_name = re.sub(rf'\b{re.escape(brand)}\b', "", clean_name, flags=re.IGNORECASE)
        
        if concentration:
            for key, val in PerfumeNormalizer.CONC_MAP.items():
                if val == concentration:
                    clean_name = re.sub(rf'\b{re.escape(key)}\b', "", clean_name, flags=re.IGNORECASE)

        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
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
