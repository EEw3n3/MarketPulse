import re
import html
from typing import Optional, Dict

class PerfumeNormalizer:
    """
    Advanced normalizer for perfume products.
    Extracts Brand, Volume, Concentration and removes noise like 'Vapo'.
    """
    
    # 1. Brands (Top common, can be expanded)
    BRANDS = [
        "Dior", "Chanel", "Giorgio Armani", "Armani", "Versace", "Gucci", "Prada", "Hermes", "Guerlain",
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
        "Acqua Di Parma", "Moschino", "Mont Blanc", "Chopard", "Jo Malone", "Le Labo",
        "By Kilian", "Bond No. 9", "Serge Lutens", "Frederic Malle", "Kilian Paris",
        "Trussardi", "Salvatore Ferragamo", "Ferragamo", "Rue Broca", "Monotheme", "Kajal", "Genyum", "Acorelle",
        "Estee Lauder", "Clinique", "Biotherm", "Viktor & Rolf", "V&R", "Diesel", "Cacharel",
        "Maison Alhambra", "Swiss Arabian", "Paris Corner", "Fragrance World",
        "Zadig & Voltaire", "Z&V", "Etro", "Missoni", "Baldessarini", "Joop!", "Nikolas de Barry",
        "Atelier Cologne", "Houbigant", "L'Artisan Parfumeur", "Miller Harris", "Tauer Perfumes",
        "Amouroud", "Omanlux", "Sospiro", "Teo Cabanel", "The Organic Pharmacy", "Yuni",
        "Aedes de Venustas", "Affinessence", "Agonist", "Altaia", "Anatole Lebreton",
        "Angela Ciampagna", "Annick Goutal", "Goutal Paris", "Areej Le Dore",
        "Abercrombie & Fitch", "Fitch", "& Fitch", "Maurer & Wirtz", "4711", "Alfred Dunhill", "Dunhill",
        "Cristiano Ronaldo", "Antonio Banderas", "Banderas",
        "Salvador Dali", "Elizabeth Taylor", "Elizabeth Arden", "Sarah Jessica Parker", "SJP",
        "Juicy Couture", "Couture", "Britney Spears", "Spears", "Katy Perry"
    ]

    BRAND_ALIASES = {
        # Aliases map SHORT/ABBREV → LONG canonical form
        "& Fitch": "Abercrombie & Fitch",
        "Fitch": "Abercrombie & Fitch",
        "JPG": "Jean Paul Gaultier",       # JPG → full name (was reversed!)
        "YSL": "Yves Saint Laurent",
        "D&G": "Dolce & Gabbana",
        "MFK": "Maison Francis Kurkdjian", # MFK → full name (was reversed!)
        "V&R": "Viktor & Rolf",
    }

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
        r"\bvīriešiem\b", r"\bmen\b", r"\bhomme\b", r"\bfor men\b",
        r"\bpour\b", r"\bfor\b", r"\bwoman\b", r"\bfemale\b", r"\bsievietēm\b",
        r"\bprocentai\b",
        r"\bintensive\b", r"\bintense\b", r"\bset\b", r"\bkomplekts\b",
        r"\bafter shave\b", r"\baftershave\b", r"\btester\b", r"\btestieris\b",
        r"\bparfums\b", r"\bman\b", r"\bwomen\b", r"\bwoman\b", r"\bmen\b",
        r"\bdezodorants\b", r"\bminiatūra\b", r"\bantiperspirants\b", r"\bantiseptiķis\b", 
        r"\baroma difuzors\b", r"\bdezodorants-zīmulis\b", r"\bdušas želeja\b",
        # Added based on stress test results
        r"\btilpums\b", r"\bvolume\b", r"\bgab\b", r"\baerosols\b", r"\baerosol\b",
        r"\bviriesiem\b", r"\bsievietem\b", r"\bvīriešu\b", r"\bsieviešu\b", r"\bviriesu\b", r"\bsieviesu\b",
        r"\bkvepalai\b", r"\bvyrams\b", r"\bmoterims\b", r"\bparfumerija\b",
        r"\btualetes ūdens\b", r"\bparfimērijas ūdens\b", r"\bsmaržūdens\b", r"\bsmaržas\b", r"\bodekolons\b",
        r"\btualetes udens\b", r"\bparfimerijas udens\b", r"\bsmarzudens\b", r"\bsmarzas\b",
        r"\beau de toilette\b", r"\beau de parfum\b", r"\bedt\b", r"\bedp\b"
    ]

    REGEX_VOLUME = re.compile(r'(\d+[.,]?\d*)\s*(ml|l|oz|мл|л)', re.IGNORECASE)

    @staticmethod
    def extract_all(title: str, explicit_brand: Optional[str] = None) -> Dict[str, Optional[str]]:
        """
        Extracts all attributes from the title.
        If explicit_brand is passed, it takes PRIORITY over heuristic brand detection.
        Heuristic detection is only used to determine what text to strip from the title.
        """
        # 0. Initial Cleanup: remove HTML entities and normalize spaces
        title = html.unescape(title)
        title_lower = title.lower()
        # 0. Preparation: remove only strictly annoying leading punctuation for brand search
        # but keep symbols that might be part of the brand (like &)
        brand_search_title = title_lower.strip("-,. |/")

        # 1. Volume
        volume = PerfumeNormalizer.extract_volume(title)

        # 2. Brand detection — heuristic scan to find what's in the title
        #    (used primarily to strip brand text from clean_name)
        all_known_brands = list(set(PerfumeNormalizer.BRANDS) | PerfumeNormalizer.DISCOVERED_BRANDS)
        sorted_brands = sorted(all_known_brands, key=len, reverse=True)

        brand_in_title: Optional[str] = None  # what was found literally in the title
        for b in sorted_brands:
            b_low = b.lower()
            eb = re.escape(b_low)
            start_b = r'\b' if b_low[0].isalnum() else r'(?:^|\s)'
            end_b = r'\b' if b_low[-1].isalnum() else r'(?:\s|$)'
            if re.search(f"{start_b}{eb}{end_b}", title_lower):
                brand_in_title = b
                break

        # Apply aliases (short → long canonical form) on the in-title detection
        brand_in_title_canonical = brand_in_title
        if brand_in_title and brand_in_title in PerfumeNormalizer.BRAND_ALIASES:
            brand_in_title_canonical = PerfumeNormalizer.BRAND_ALIASES[brand_in_title]

        # 3. Determine the AUTHORITATIVE brand:
        #    explicit_brand > detected-in-title > heuristic first-word
        if explicit_brand:
            # explicit_brand wins unconditionally — caller knows best
            brand = explicit_brand
        elif brand_in_title_canonical:
            brand = brand_in_title_canonical
        else:
            # Heuristic: first word as brand (only when no explicit and nothing found)
            brand = None
            words = title.split()
            if words:
                first_word = words[0].strip(",.- ")
                forbidden_heuristics = {
                    "man", "men", "woman", "women", "homme", "femme",
                    "for", "pour", "the", "with", "eau", "de", "parfum"
                }
                is_valid = (
                    first_word.lower() not in forbidden_heuristics
                    and first_word.lower() not in PerfumeNormalizer.CONC_MAP
                    and not any(
                        re.search(rf'\b{re.escape(first_word.lower())}\b', noise, re.IGNORECASE)
                        for noise in PerfumeNormalizer.NOISE
                    )
                )
                if is_valid:
                    brand = first_word
                    if len(first_word) <= 3 and len(words) > 1:
                        second_word = words[1].strip(',.- ')
                        if second_word.lower() not in forbidden_heuristics:
                            brand = f"{first_word} {second_word}"
        
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
        # Save pre-noise state as fallback (e.g. "Pour Homme" must survive noise removal)
        _before_noise = re.sub(r'\s+', ' ', clean_name).strip()
        for noise_pat in PerfumeNormalizer.NOISE:
            clean_name = re.sub(noise_pat, "", clean_name, flags=re.IGNORECASE)

        # Strip the brand text that actually appears in the title.
        # We use brand_in_title (raw detected form) for removal, NOT the explicit_brand,
        # because if the caller passed explicit_brand the brand text may not be in the title at all.
        if brand_in_title:
            b_low = brand_in_title.lower()
            eb = re.escape(b_low)
            start_b = r'\b' if b_low[0].isalnum() else r'(?:^|\s)'
            end_b = r'\b' if b_low[-1].isalnum() else r'(?:\s|$)'
            clean_name = re.sub(f"{start_b}{eb}{end_b}", " ", clean_name, flags=re.IGNORECASE)
            # Also remove alias-expanded canonical form if it's literally in the title
            if brand_in_title_canonical and brand_in_title_canonical != brand_in_title:
                b_low2 = brand_in_title_canonical.lower()
                eb2 = re.escape(b_low2)
                start_b2 = r'\b' if b_low2[0].isalnum() else r'(?:^|\s)'
                end_b2 = r'\b' if b_low2[-1].isalnum() else r'(?:\s|$)'
                clean_name = re.sub(f"{start_b2}{eb2}{end_b2}", " ", clean_name, flags=re.IGNORECASE)

        if concentration:
            for key, val in PerfumeNormalizer.CONC_MAP.items():
                if val == concentration:
                    clean_name = re.sub(rf'\b{re.escape(key)}\b', "", clean_name, flags=re.IGNORECASE)

        # Brand-segment word cleanup — only when brand was detected FROM THE TITLE
        # (not from explicit_brand), to avoid incorrectly stripping product-name words.
        # E.g. "Giorgio Armani Emporio Armani..." → after removing "Giorgio Armani" phrase,
        # the stray "Armani" still remains; remove it. But "Emporio" is a product word, keep it.
        # When explicit_brand is given (brand not found in title), we DO NOT have certainty
        # which brand tokens appear as orphans vs product name words, so we skip this.
        if brand_in_title:
            # brand_in_title_canonical may differ from brand (via explicit_brand override),
            # use canonical of what was actually in the title for orphan cleanup.
            _cleanup_brand = brand_in_title_canonical or brand_in_title
            for _bseg in _cleanup_brand.split():
                if len(_bseg) > 3:  # skip short tokens like "de", "&"
                    _eb_bseg = re.escape(_bseg.lower())
                    clean_name = re.sub(rf'\b{_eb_bseg}\b', " ", clean_name, flags=re.IGNORECASE)

        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
        
        # Aggressive word-by-word cleanup for orphan generic words
        generic_words = {
            "eau", "parfum", "edt", "edp", "pour", "for", "de", "man", "men", "woman", "women", "homme", "femme", "set",
            "gab", "tilpums", "volume", "vīriešiem", "sievietēm", "viriesiem", "sievietem", "vīriešu", "sieviešu",
            "tualetes", "ūdens", "parfimērijas", "smaržas", "kvepalai", "vyrams", "moterims", "parfumerija"
        }
        words = clean_name.split()
        filtered_words = [w for w in words if w.lower().strip("-,.:|") not in generic_words]
        clean_name = " ".join(filtered_words)

        # FALLBACK: trigger if clean_name is empty OR consists only of words
        # that are part of the brand name (e.g. "HUGO" left over from "Hugo Boss")
        _brand_words = {w.lower() for w in (brand or "").split() if len(w) > 2}
        _clean_words = {w.lower().strip("-,.") for w in clean_name.split()}
        _is_brand_fragment = bool(_clean_words) and _clean_words.issubset(_brand_words)

        if (len(clean_name) <= 2 or _is_brand_fragment) and len(_before_noise) > 2:
            _fallback = _before_noise
            # Remove full brand string (phrase)
            if brand_in_title:
                b_low_f = brand_in_title.lower()
                eb_f = re.escape(b_low_f)
                sb_f = r'\b' if b_low_f[0].isalnum() else r'(?:^|\s)'
                eb_f2 = r'\b' if b_low_f[-1].isalnum() else r'(?:\s|$)'
                _fallback = re.sub(f"{sb_f}{eb_f}{eb_f2}", " ", _fallback, flags=re.IGNORECASE)
            # Remove canonical brand phrase
            if brand and brand != brand_in_title:
                b_low_f2 = brand.lower()
                eb_f3 = re.escape(b_low_f2)
                sb_f2 = r'\b' if b_low_f2[0].isalnum() else r'(?:^|\s)'
                eb_f4 = r'\b' if b_low_f2[-1].isalnum() else r'(?:\s|$)'
                _fallback = re.sub(f"{sb_f2}{eb_f3}{eb_f4}", " ", _fallback, flags=re.IGNORECASE)
            # Also remove individual brand words (handles partial matches like "HUGO" from "Hugo Boss")
            for _bw in _brand_words:
                _fallback = re.sub(rf'\b{re.escape(_bw)}\b', " ", _fallback, flags=re.IGNORECASE)
            # Remove concentration
            if concentration:
                for key, val in PerfumeNormalizer.CONC_MAP.items():
                    if val == concentration:
                        _fallback = re.sub(rf'\b{re.escape(key)}\b', "", _fallback, flags=re.IGNORECASE)
            # Only strip truly useless words — keep 'pour homme', 'man', 'intense', etc.
            _min_filter = {"eau", "parfum", "edt", "edp", "de", "set"}
            _fallback = " ".join(w for w in _fallback.split() if w.lower().strip("-,.") not in _min_filter)
            _fallback = _fallback.strip("-,. |/")
            if len(_fallback) > 2:
                clean_name = _fallback

        # If clean_name is too short or just common words, it's garbage
        if len(clean_name) <= 2:
            clean_name = ""

        # Remove orphan hyphens/commas/pipes
        clean_name = re.sub(r'^[,\-\|\s]+|[,\-\|\s]+$', '', clean_name)
        # Final cleanup for punctuation artifacts (e.g. "Name - ")
        clean_name = clean_name.strip("-,. |/")

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
