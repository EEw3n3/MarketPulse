import re
import html
import unicodedata
from typing import Optional, Dict

from thefuzz import fuzz

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
        "Burberry", "Gisada", "Clive Christian", "BellaVita", "Afnan",
        "Jacques Zolty", "Arabiyat Prestige", "Maison Alhambra", "Bugatti",
        "Cristiano Ronaldo", "Antonio Banderas", "Banderas",
        "Davidoff", "Adidas", "Hermès", "Boucheron", "Van Cleef & Arpels",
        "La Rive", "Ungaro", "Emanuel Ungaro", "Cerruti", "Nino Cerruti",
        "BI-ES", "Jacques Bogart", "Nikos", "Bruno Banani", "Jesus Del Pozo",
        "Moncler", "Mercedes-Benz", "18.21. Man Made", "Chabaud",
        "Salvador Dali", "Elizabeth Taylor", "Elizabeth Arden", "Sarah Jessica Parker", "SJP",
        "Juicy Couture", "Couture", "Britney Spears", "Spears", "Katy Perry",
        # Shops spell these with or without accents / spaces around "&"; the
        # entry here is the form every spelling is shown as (see canonical_brand).
        "Etat Libre d'Orange", "Courrèges", "Acqua dell'Elba", "Roger & Gallet",
        "Stéphane Humbert Lucas 777", "Instituto Español", "Floraïku", "Maison Tahité",
        "Mont St. Michel", "Tiffany & Co", "Histoires de Parfums", "Les Liquides Imaginaires",
        "Ralph Lauren", "Lattafa", "Alfred Dunhill", "Annick Goutal", "Etienne Aigner",
        "Hugh Parsons", "Kajal", "Roja Parfums",
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
        "parfimēts ūdens": "EDP",
        "parfimets udens": "EDP",
        "aromatizēts ūdens": "EDP",  # makeup.lv's label for Eau de Parfum
        "aromatizets udens": "EDP",
        "parfīms": "EDP",  # douglas.lv; Ervin's call (Douglas's own data mostly says EDP)
        "parfims": "EDP",
        "parfimēts eliksīrs": "EDP",  # douglas.lv
        "parfimets eliksirs": "EDP",
        "aromāta ekstrakts": "Parfum",  # douglas.lv: Extrait
        "aromata ekstrakts": "Parfum",
        "aromatizēts ekstrakts": "Parfum",  # notino.lv: Extrait (Ervin: same as Aromāta ekstrakts)
        "aromatizets ekstrakts": "Parfum",
        "smaržu ekstrakts": "Parfum",  # douglas.lv: Extrait
        "smarzu ekstrakts": "Parfum",
        "smaržu eliksīrs": "Parfum",  # douglas.lv; Ervin: same as Smaržas
        "smarzu eliksirs": "Parfum",
        "eliksīrs": "Parfum",  # douglas.lv (Dior Sauvage Elixir); Ervin's call
        "eliksirs": "Parfum",
        "parfimērijas ekstrakts": "EDP",  # douglas.lv (Ramon Monegal); other shops say EDP
        "parfimerijas ekstrakts": "EDP",
        "parfimerijas ūdens": "EDP",  # douglas.lv spelling without ē
        "smaržūdens": "EDP",
        # 220.lv sellers' spellings (Ervin, 2026-10-03)
        "parfimētais ūdens": "EDP",
        "parfimetais udens": "EDP",
        "parfīmētais ūdens": "EDP",
        "parfīmétais ūdens": "EDP",
        "parfumētais ūdens": "EDP",
        "parfumēts ūdens": "EDP",
        "parfumetais udens": "EDP",
        "parfumets udens": "EDP",
        "parfūmēts ūdens": "EDP",
        "parfūmētais ūdens": "EDP",
        "parfīma ūdens": "EDP",
        "parfima udens": "EDP",
        "parfīmūdens": "EDP",
        "parfūmjūdens": "EDP",
        "parfīmierūdens": "EDP",
        "parfumūdens": "EDP",
        "smaržu ūdens": "EDP",
        "smaržīgs ūdens": "EDP",
        "aromatizētais ūdens": "EDP",
        "parfumuotas vanduo": "EDP",  # Lithuanian
        "parfüms": "EDP",  # same as "parfīms"
        "tualetinis ūdens": "EDT",
        "tualetinis vanduo": "EDT",  # Lithuanian
        "tualtais ūdens": "EDT",
        "toilet water": "EDT",
        "toilette": "EDT",
        "e dt": "EDT",
        "odikolons": "EDC",
        "kolonijas ūdens": "EDC",
        "kolēnija": "EDC",
        "kelnūdens": "EDC",
        "kolo toniks": "EDC",
        "cologne": "EDC",
        "kvepalai": "Parfum",  # Lithuanian "perfume", like "smaržas"
        "ekstrakts": "Parfum",
        "edt": "EDT",
        "eau de toilette": "EDT",
        "tualetes ūdens": "EDT",
        "parfum": "Parfum",
        "pure parfum": "Parfum",
        "extrait de parfum": "Parfum",
        "smaržas": "Parfum",
        "edc": "EDC",
        "eau de cologne": "EDC",
        "odekolons": "EDC",
        "odekalons": "EDC",  # makeup.lv misspelling
    }

    # 3. Noise to ignore
    NOISE = [
        r"\bvapo\b", r"\bvaporisateur\b", r"\bspray\b", r"\bnatural spray\b",
        # English "Man" / "Pour Homme" / "For Him" stay: they are part of the
        # names ("Hugo Man", "Versace Pour Homme", "Narciso Rodriguez For Him").
        # name_key() ignores them when comparing names.
        r"\bsievietei\s+un\s+vīrietim\b", r"\bvīrietim\s+un\s+sievietei\b",
        r"\bvīriešiem\b", r"\bfemale\b", r"\bsievietēm\b",
        r"\bvīrietim\b", r"\bvirietim\b", r"\bsievietei\b",  # douglas.lv type line
        r"\bprocentai\b",
        # NOTE: 'intense' / 'intensive' INTENTIONALLY removed from NOISE.
        # Words like "Intense" are PRODUCT-LINE distinguishers — "Dior Sauvage"
        # and "Dior Sauvage Intense" are entirely different perfumes, but
        # stripping the word made them chain into one group. Same with
        # "Le Male" vs "Le Male Intense", etc.
        r"\bset\b", r"\bkomplekts\b",
        r"\bafter shave\b", r"\baftershave\b", r"\btester\b", r"\btestieris\b",
        r"\bparfums\b",
        r"\bdezodorants\b", r"\bantiperspirants\b", r"\bantiseptiķis\b",
        # A miniature is the same perfume in a small bottle: drop the marker so
        # it joins the full-size group ("10 ml *miniatūra", "EDT Miniature, 5 ml").
        # A bare "mini" is dropped only for small volumes (see MINI_MAX_ML).
        r"\*?\s*\bminiatūra\b", r"\*?\s*\bminiatūras\b", r"\*?\s*\bminiatura\b",
        r"\*?\s*\bminiature\b", r"\*?\s*\bminiatures\b",
        r"\baroma difuzors\b", r"\bdezodorants-zīmulis\b", r"\bdušas želeja\b",
        # Added based on stress test results
        r"\btilpums\b", r"\bvolume\b", r"\bgab\b", r"\baerosols\b", r"\baerosol\b",
        r"\bviriesiem\b", r"\bsievietem\b", r"\bvīriešu\b", r"\bsieviešu\b", r"\bviriesu\b", r"\bsieviesu\b",
        r"\bkvepalai\b", r"\bvyrams\b", r"\bmoterims\b", r"\bparfumerija\b",
        r"\btualetes ūdens\b", r"\bparfimērijas ūdens\b", r"\bsmaržūdens\b", r"\bsmaržas\b", r"\bodekolons\b",
        r"\btualetes udens\b", r"\bparfimerijas udens\b", r"\bsmarzudens\b", r"\bsmarzas\b",
        r"\beau de toilette\b", r"\beau de parfum\b", r"\bedt\b", r"\bedp\b", r"\bedc\b",
        # Latvian artifacts that survive CONC_MAP stripping but pollute clean_name
        r"\bar\s+uzpildīšānas\s+iespēju\b", r"\buzpildīšānas\b", r"\buzpildāms\b", r"\buzpildes\b",
        r"\bar\s+uzpildīsanas\s+iespēju\b", r"\buzpildisanas\b", r"\buzpildams\b",
        r"\bizsmidzināms\b", r"\bizsmidzinams\b",
        r"\babiem\s+dzimumiem\b", r"\bdzimumiem\b",
        r"\bviriešu\b", r"\bvīrieši\b", r"\bvīriesi\b",  # genitive/nominative variants
        r"\bsievietes\b", r"\bsievietēm\b",
        r"\baerosols\b",  # explicitly add (was accidentally losing word boundary in some cases)
        r"\(\s*\)",       # orphan empty brackets left after stripping (EDT)/(EDP)
        # Pack variants: the perfume is the same, the pack goes into the volume
        # label instead (see volume_qualifier); "refillable" is a normal bottle.
        r"\brefill\b", r"\brefillable\b", r"\buzpilde\b", r"\bwithout stand\b", r"\bbez statīva\b",
        r"\blimited edition\b", r"\+\s*case\b", r"\bwith case\b",
        # 220.lv: "mini 10 ml ar melnu ceļojuma futlāri" = with a (black) travel case
        r"\bar\s+(?:\w+\s+)?ceļojuma\s+futlār\w*",
        # Session 5 additions
        r"\bparfimēts\b", r"\bparfimets\b",
        r"\bsmaržu\b",
        r"\buzpildāmais\b", r"\buzpildamais\b",
        # NOTE: 'bottled' is intentionally NOT in NOISE — it is part of real
        # product names (e.g. Hugo Boss Bottled). `pudelēs pildīts` is
        # normalized to 'Bottled' in extract_all() so LV and EN forms match.
        # Session 5 follow-up additions
        r"\bunisex\b",
        r"\bpapildinājums\b", r"\bpapildinajums\b",
        r"\baromāts\b", r"\baromats\b", r"\baromātu\b", r"\baromatu\b",
        # Session 17 — Notino LV "limited edition" parenthetical artifact:
        # "(ierobežota daudzuma prece)" = "limited quantity item". Strip the
        # individual words; the orphan-bracket pattern above clears the empty ().
        r"\bierobežota\b", r"\bierobezota\b",
        r"\bdaudzuma\b", r"\bdaudzums\b",
        r"\bprece\b", r"\bpreces\b",
    ]

    # Latvian ↔ English canonical replacements applied before NOISE stripping.
    # Purpose: enable cross-site chaining between localized variants (e.g.
    # "Hugo Boss pudelēs pildīts 30ml" on a LV site must match
    # "Hugo Boss Bottled 30ml" on an EN/mixed site).
    LOCALIZATION_MAP = [
        (re.compile(r'\bpudelēs\s+pildīts\b', re.IGNORECASE), 'Bottled'),
        (re.compile(r'\bpudeles\s+pildits\b', re.IGNORECASE), 'Bottled'),
    ]

    # The unit must end the word: "STR8 Live" is not "8 L", "5 gab." is not "5 g".
    REGEX_VOLUME = re.compile(r'(\d+[.,]?\d*)\s*(ml|l|oz|g|мл|л|г)\b', re.IGNORECASE)

    # Labels that can also be part of a perfume's name ("Creed Viking Cologne EDP",
    # "Eternity for Men Cologne EDT"): they count only when no other EDT/EDP/EDC
    # marker is in the title.
    WEAK_CONC_KEYS = {"cologne", "toilette"}
    # ...and "Cologne" stays in the name ("Dior Homme Cologne", "Fierce Cologne"),
    # as in the groups created before it became a label.
    CONC_KEYS_KEPT_IN_NAME = {"cologne"}

    # "mini" marks a miniature only on a small bottle ("Vetiver Musc mini 10 ml",
    # "Dear Barber mini 30 ml"); in "Immortal Mini 150 ml" or "Pride Collection
    # Mini 01" it is the name.
    MINI_MAX_ML = 30
    REGEX_MINI = re.compile(r'\bmini\b', re.IGNORECASE)

    # "Le Parfum" names a line ("Y Le Parfum", "Paradigme Le Parfum"): the
    # concentration is Parfum, but the words stay in the name. The placeholder
    # is one word, so the Parfum label stripping cannot touch it.
    REGEX_LE_PARFUM = re.compile(r"\ble\s+parfum\b", re.IGNORECASE)
    LE_PARFUM_PLACEHOLDER = "le_parfum_kept"

    @staticmethod
    def extract_all(title: str, explicit_brand: Optional[str] = None) -> Dict[str, Optional[str]]:
        """
        Extracts all attributes from the title.
        If explicit_brand is passed, it takes PRIORITY over heuristic brand detection.
        Heuristic detection is only used to determine what text to strip from the title.
        """
        # 0. Initial Cleanup: remove HTML entities and normalize spaces
        title = html.unescape(title)
        # Localization: map Latvian phrases to their English canonical form
        # BEFORE any further processing, so both sides chain symmetrically.
        for _loc_re, _loc_repl in PerfumeNormalizer.LOCALIZATION_MAP:
            title = _loc_re.sub(_loc_repl, title)
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
            # Heuristic: first non-forbidden word as brand
            brand = None
            words = title.split()
            forbidden_heuristics = {
                "man", "men", "woman", "women", "homme", "femme",
                "for", "pour", "the", "with", "eau", "de", "parfum",
                # Latvian product type prefixes (all grammatical forms)
                "vīriešu", "sieviešu", "tualetes", "parfimērijas", "smaržas",
                "smaržūdens", "odekolons", "viriesu", "sieviesu",
                "smaržu", "uzpildes",  # genitive form + refill indicator
            }
            for i, raw_word in enumerate(words):
                candidate = raw_word.strip(",.- ")
                cand_low = candidate.lower()
                if not candidate:
                    continue
                if cand_low in forbidden_heuristics:
                    continue
                if cand_low in PerfumeNormalizer.CONC_MAP:
                    continue
                if any(re.search(rf'\b{re.escape(cand_low)}\b', noise, re.IGNORECASE)
                       for noise in PerfumeNormalizer.NOISE):
                    continue
                # Found the first valid word — use it as brand candidate
                brand = candidate
                # Short prefix (≤3 chars like "YSL", "CK", "La") → try to grab next word too
                if len(candidate) <= 3 and i + 1 < len(words):
                    next_word = words[i + 1].strip(',.- ')
                    if next_word.lower() not in forbidden_heuristics:
                        brand = f"{candidate} {next_word}"
                break
        
        # One spelling per brand ("HERMÈS" / "Hermes" → "Hermès", "ARMANI" → "Giorgio Armani")
        brand = canonical_brand(brand)

        # 4. Concentration
        # Priority: specific EDT/EDP/EDC markers first; generic "Parfum"/"Smaržas"
        # last (they're fallback labels that should lose to explicit EDT/EDP in the same title).
        concentration = None
        sorted_conc_keys = sorted(
            PerfumeNormalizer.CONC_MAP.keys(),
            key=lambda k: (k in PerfumeNormalizer.WEAK_CONC_KEYS,
                           PerfumeNormalizer.CONC_MAP[k] == "Parfum", -len(k))
        )
        for key in sorted_conc_keys:
            pattern = rf'\b{re.escape(key)}\b'
            # A weak label inside the brand ("Atelier Cologne") is not a label.
            if key in PerfumeNormalizer.WEAK_CONC_KEYS and brand and re.search(pattern, brand.lower()):
                continue
            if re.search(pattern, title_lower):
                concentration = PerfumeNormalizer.CONC_MAP[key]
                break

        # 5. Clean Name: the title minus volume, labels, noise and the brand in
        # front. Words of the name itself stay, even when they repeat the brand
        # ("Terre d'Hermès", "Bleu de Chanel", "Escentric 02") or look generic
        # ("Pour Homme", "Club de Nuit", "Y").
        brand_keys = {brand_key(b) for b in (brand, brand_in_title) if b}
        clean_name = PerfumeNormalizer.REGEX_VOLUME.sub("", title)
        clean_name = PerfumeNormalizer.REGEX_LE_PARFUM.sub(PerfumeNormalizer.LE_PARFUM_PLACEHOLDER, clean_name)
        # Brand first: noise like "Parfums" can be part of it ("Parfums de Marly").
        clean_name = strip_leading_brand(clean_name, brand_keys)
        # Labels before noise, longest first, so a phrase goes as a whole
        # ("Parfimēts eliksīrs", "Extrait de Parfum").
        if concentration:
            for key in sorted(PerfumeNormalizer.CONC_MAP, key=len, reverse=True):
                if (PerfumeNormalizer.CONC_MAP[key] == concentration
                        and key not in PerfumeNormalizer.CONC_KEYS_KEPT_IN_NAME):
                    clean_name = re.sub(rf'\b{re.escape(key)}\b', "", clean_name, flags=re.IGNORECASE)
        for noise_pat in PerfumeNormalizer.NOISE:
            clean_name = re.sub(noise_pat, "", clean_name, flags=re.IGNORECASE)
        if PerfumeNormalizer.is_mini_volume(volume):
            clean_name = PerfumeNormalizer.REGEX_MINI.sub("", clean_name)

        # Orphan label words left after the stripping above
        generic_words = {
            "parfum", "edt", "edp", "edc", "set",
            "gab", "tilpums", "volume", "vīriešiem", "sievietēm", "viriesiem", "sievietem", "vīriešu", "sieviešu",
            "tualetes", "ūdens", "parfimērijas", "smaržas", "kvepalai", "vyrams", "moterims", "parfumerija"
        }
        words = clean_name.split()
        clean_name = " ".join(w for w in words if w.lower().strip("-,.:|") not in generic_words
                              and any(c.isalnum() for c in w))
        # Again after the noise: shops put the type in front ("Tualetes ūdens
        # Hugo Boss Boss Bottled", "CALVIN KLEIN - Calvin Klein CK IN2U") and
        # 220.lv sellers the brand last ("Legend Spirit Montblanc").
        clean_name = strip_trailing_brand(strip_leading_brand(clean_name, brand_keys), brand_keys)
        clean_name = clean_name.replace(PerfumeNormalizer.LE_PARFUM_PLACEHOLDER, "Le Parfum")
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()

        # Remove orphan hyphens/dashes/commas/pipes ("Dear Barber – Eau de Toilette – …")
        clean_name = re.sub(r'^[,\-–—\|\s]+|[,\-–—\|\s]+$', '', clean_name)
        # Final cleanup for punctuation artifacts (e.g. "Name - ")
        clean_name = clean_name.strip("-–—,. |/:?!")
        # Nothing but punctuation left
        if not any(c.isalnum() for c in clean_name):
            clean_name = ""

        return {
            "brand": brand,
            "volume": volume,
            "concentration": concentration,
            "clean_name": clean_name
        }

    @staticmethod
    def is_mini_volume(volume: Optional[str]) -> bool:
        """True for a miniature-size volume as extract_volume() writes it ("10ml")."""
        m = re.fullmatch(r'(\d+(?:\.\d+)?)ml', volume or "")
        return bool(m) and float(m.group(1)) <= PerfumeNormalizer.MINI_MAX_ML

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
                elif unit in ['g', 'г']: unit = 'g'  # solid perfume

                if amount.is_integer(): return f"{int(amount)}{unit}"
                return f"{round(amount, 1)}{unit}"
            except: return None
        return None

perfume_normalizer = PerfumeNormalizer()


def _fold(text: str) -> str:
    """Lowercase ASCII form: accents dropped ("Hermès" → "hermes"), apostrophes
    removed ("d'Hermès" → "dhermes")."""
    text = unicodedata.normalize("NFKD", html.unescape(text or ""))
    text = text.encode("ascii", "ignore").decode().lower()
    return re.sub(r"['’`´]", "", text)


# Words a shop adds to a brand ("Lattafa Perfumes", "Memo Paris", "Roja Parfums").
_BRAND_KEY_SUFFIXES = {"perfumes", "perfume", "parfums", "paris", "beauty"}
# Different names of one brand, as brand keys (see brand_key).
_BRAND_KEY_ALIASES = {
    "armani": "giorgioarmani",
    "boss": "hugoboss",
    "pacorabanne": "rabanne",
    "alhambra": "maisonalhambra",
    "banderas": "antoniobanderas",
    "ferragamo": "salvatoreferragamo",
    "dunhill": "alfreddunhill",
    "liquidesimaginaires": "lesliquidesimaginaires",
    "acquadi": "acquadiparma",  # makeup.lv cuts "Acqua Di Parma" to "AcquaDi"
    "houseof4711": "4711",
    "aigner": "etienneaigner",
    "hughparson": "hughparsons",
    "bogart": "jacquesbogart",
    "goutal": "annickgoutal",
    "lagerfeld": "karllagerfeld",
    "bykilian": "kilian",
    "ungaro": "emanuelungaro",
    "christiandior": "dior",
    "bulgari": "bvlgari",
    "abanderas": "antoniobanderas",  # 220.lv sellers: "A. Banderas", "J.P. Gaultier"
    "jpgaultier": "jeanpaulgaultier",
}


def brand_key(brand: Optional[str]) -> str:
    """Comparison key of a brand: case, accents, spaces and punctuation don't
    count, shop suffixes and known aliases are resolved ("HERMÈS" = "Hermes",
    "Dolce&Gabbana" = "D&G", "ARMANI" = "Giorgio Armani")."""
    words = re.sub(r"[^a-z0-9]+", " ", _fold(brand or "")).split()
    while len(words) > 1 and words[-1] in _BRAND_KEY_SUFFIXES:
        words.pop()
    key = "".join(words)
    key = _BRAND_KEY_ALIASES.get(key, key)
    alias = PerfumeNormalizer.BRAND_ALIASES
    for short, long_form in alias.items():  # YSL, JPG, D&G, MFK, V&R, Fitch
        if key == re.sub(r"[^a-z0-9]", "", _fold(short)):
            return re.sub(r"[^a-z0-9]", "", _fold(long_form))
    return key


# Display form per brand key: the first BRANDS entry wins, except where the
# accented spelling should.
_BRAND_DISPLAY: Dict[str, str] = {"hermes": "Hermès", "rabanne": "Rabanne"}
for _b in PerfumeNormalizer.BRANDS:
    _BRAND_DISPLAY.setdefault(brand_key(_b), _b)


def canonical_brand(brand: Optional[str]) -> Optional[str]:
    """One display spelling per brand. Known brands take their BRANDS form;
    an unknown brand written in capitals (douglas.lv) is title-cased."""
    if not brand:
        return brand
    brand = re.sub(r"\s+", " ", html.unescape(brand)).strip()
    known = _BRAND_DISPLAY.get(brand_key(brand))
    if known:
        return known
    if brand.isupper() and len(brand) > 4:
        # "L'ERBOLARIO" → "L'Erbolario", "KIEHL'S" → "Kiehl's"
        brand = re.sub(r"[^\W\d_]+", lambda m: m.group(0).capitalize(), brand.lower())
        brand = re.sub(r"(?<=\w['’])([A-Z])\b", lambda m: m.group(1).lower(), brand)
    return brand


def strip_leading_brand(text: str, brand_keys: set[str]) -> str:
    """Drop the brand from the start of a title, as often as it repeats there
    ("Hugo Boss Boss Bottled" → "Bottled", "CALVIN KLEIN - Calvin Klein CK IN2U"
    → "IN2U"). A brand word later in the name stays ("Terre d'Hermès")."""
    brand_keys = {k for k in brand_keys if k}
    while brand_keys:
        stripped = text.lstrip(" -–—,.|/:")
        words = stripped.split()
        cut = next((n for n in range(min(len(words), 6), 0, -1)
                    if brand_key(" ".join(words[:n])) in brand_keys), 0)
        if not cut:
            return stripped
        text = " ".join(words[cut:])
    return text


def strip_trailing_brand(text: str, brand_keys: set[str]) -> str:
    """Drop the brand from the end of a title ("Legend Spirit Montblanc",
    "The Scent Hugo Boss"), but not where it belongs to the name ("Bleu de
    Chanel", "K by Dolce & Gabbana", "L'Eau Par Kenzo")."""
    brand_keys = {k for k in brand_keys if k}
    words = text.rstrip(" -–—,.|/:").split()
    for n in range(min(len(words) - 1, 6), 0, -1):
        if brand_key(" ".join(words[-n:])) in brand_keys:
            if _fold(words[-n - 1]).strip(",.-") in {"de", "d", "di", "du", "by", "par", "of", "pour", "for"}:
                break
            return " ".join(words[:-n])
    return " ".join(words)


# Words that don't tell two perfumes apart when names are compared.
# "parfum" is left only by "Le Parfum", which older titles cut to "Le";
# "s" by "Men's".
_NAME_FILLER = {"de", "di", "du", "d", "of", "the", "and", "et", "by", "pour", "for", "per", "parfum", "s"}
_MALE_WORDS = {"man", "men", "homme", "him", "uomo", "hombre"}
_FEMALE_WORDS = {"woman", "women", "femme", "her", "donna", "mujer", "lady"}
# Shop words for the same thing ("intensīvs" = "Intense").
_NAME_SYNONYMS = {"intensivs": "intense"}
# Short forms of a brand inside names ("CK One", "A. Banderas The Secret").
_BRAND_EXTRA_WORDS = {
    "calvinklein": {"ck"}, "yvessaintlaurent": {"ysl"}, "dolcegabbana": {"dg"},
    "jeanpaulgaultier": {"jpg", "jp", "j", "p"}, "antoniobanderas": {"a"}, "4711": {"house"},
}
# Words a typo away from each other that still name different perfumes.
_DIFFERENT_WORDS = {frozenset({"intense", "intensely"}), frozenset({"intense", "intensive"})}
_brand_words_cache: dict[str, frozenset[str]] = {}


def _brand_words(brand: Optional[str]) -> frozenset[str]:
    """Words of every spelling of the brand ("Giorgio Armani" → giorgio, armani)."""
    key = brand_key(brand)
    if key not in _brand_words_cache:
        spellings = [b for b in PerfumeNormalizer.BRANDS if brand_key(b) == key]
        spellings.append(canonical_brand(brand) or "")
        words = {w for b in spellings for w in re.sub(r"[^a-z0-9]+", " ", _fold(b)).split()}
        _brand_words_cache[key] = frozenset(words | _BRAND_EXTRA_WORDS.get(key, set()))
    return _brand_words_cache[key]


def name_key(clean_name: Optional[str], brand: Optional[str] = None) -> dict:
    """What matters when two names are compared: the words without filler,
    gender words and brand words ("Pour Homme" or "Boss" add nothing to
    "Hugo Boss Boss Bottled Pour Homme"), plus the gender the words name.
    A name made only of such words keeps the brand words, then the gender
    words ("Hugo Man" = "Hugo", "Pour Homme")."""
    words = [_NAME_SYNONYMS.get(w, w) for w in re.sub(r"[^a-z0-9]+", " ", _fold(clean_name or "")).split()]
    brand_words = _brand_words(brand) if brand else frozenset()
    gender = None
    if _MALE_WORDS & set(words):
        gender = "male"
    if _FEMALE_WORDS & set(words):
        gender = None if gender else "female"
    # "d'Hermès" / "L'Issey" count as brand words too: older titles lost them.
    core = [w for w in words if w not in _NAME_FILLER and w not in _MALE_WORDS
            and w not in _FEMALE_WORDS and w not in brand_words
            and not (len(w) > 3 and w[0] in "dl" and w[1:] in brand_words)]
    if not core:  # "Hugo Man" → hugo, "Pour Homme" → homme
        core = ([w for w in words if w not in _NAME_FILLER and w not in _MALE_WORDS and w not in _FEMALE_WORDS]
                or [w for w in words if w not in _NAME_FILLER] or words)
    return {"words": sorted(set(core)), "gender": gender}


def _same_word(a: str, b: str) -> bool:
    """Equal, or a typo in a long word ("Supremacy" / "Supermacy", "Vanilla" /
    "Vanille"); never across digits or the pairs in _DIFFERENT_WORDS."""
    if a == b:
        return True
    if min(len(a), len(b)) < 6 or any(c.isdigit() for c in a + b) or frozenset({a, b}) in _DIFFERENT_WORDS:
        return False
    return fuzz.ratio(a, b) >= 85


def names_match(a: dict, b: dict) -> bool:
    """True when two name_key() results name the same perfume. Every word must
    have its twin on the other side (a typo in a long word is forgiven), so
    "Molecule 01" ≠ "Molecule 02", "Sauvage" ≠ "Eau Sauvage" and "Intense" ≠
    "Intensely"."""
    if a["gender"] and b["gender"] and a["gender"] != b["gender"]:
        return False
    wa, wb = a["words"], b["words"]
    if wa == wb:
        return True
    if not wa or not wb or len(wa) != len(wb):
        return False
    return all(any(_same_word(w, v) for v in y) for x, y in ((wa, wb), (wb, wa)) for w in x)
    if not wa or not wb or len(wa) != len(wb):
        return False
    if {w for w in wa if any(c.isdigit() for c in w)} != {w for w in wb if any(c.isdigit() for c in w)}:
        return False
    for x, y in ((wa, wb), (wb, wa)):
        for w in x:
            if w not in y and not any(fuzz.ratio(w, v) >= 90 for v in y):
                return False
    return True


# Markers that prove a listing is NOT a perfume (deodorants, body sprays,
# aftershaves, shower gels, hair products, etc.). Used at scrape time to
# reject pollution BEFORE it enters the DB. Word-bounded compounds only —
# bare 'spray' or 'stick' is allowed because real perfumes use those words.
_NON_PERFUME_PATTERNS = [
    # Deodorants / antiperspirants
    r"\bdeodorants?\b", r"\bdeo[\s\-]?spray\b", r"\bdeo[\s\-]?stick\b",
    r"\bdeo[\s\-]?roll[\s\-]?on\b", r"\bantiperspirants?\b",
    r"\banti[\s\-]?perspirants?\b", r"\bdezodorants?\b",
    r"\bdezodorants[\s\-]?(zīmulis|aerosols|sprejs)\b",
    r"\bдезодорант\w*\b", r"\bдезо[\-\s]?(спрей|стик|ролик)\b",
    # Body / shower products — NOTE: 'body mist' / 'hair mist' EXCLUDED
    # because they're legit fragrance categories (Ex Nihilo, Sol de Janeiro,
    # Byredo, Victoria's Secret all sell perfumed mists). 'body spray' is
    # safe to filter — that label is reserved for non-perfume deodorants.
    r"\bbody[\s\-]?spray\b", r"\bbody[\s\-]?lotion\b",
    r"\bbody[\s\-]?wash\b", r"\bshower[\s\-]?gel\b", r"\bbath[\s\-]?gel\b",
    r"\bdušas[\s\-]?(želeja|gels)\b", r"\bdušas[\s\-]?želeja\b",
    r"\bгель\s+для\s+душа\b", r"\bлосьон\s+для\s+тела\b",
    # Hair (excluded 'mist' — see note above)
    r"\bshampoo\b", r"\bšampūns?\b", r"\bшампунь\w*\b",
    r"\bconditioner\b", r"\bkondicionieris\b", r"\bкондиционер\w*\b",
    r"\bhair[\s\-]?(spray|gel|oil|mask)\b",
    # Aftershave / pre-shave
    r"\baftershave\b", r"\bafter[\s\-]shave\b",
    r"\bpēc[\s\-]?skūšanās\b", r"\bпосле[\s\-]бритья\b",
    # Powders / soaps / lotions / creams
    r"\btalcum\b", r"\btalk[\s\-]?puderis\b", r"\bbody[\s\-]?talc\b",
    r"\bbar[\s\-]?soap\b", r"\bziepes\b", r"\bмыло\b",
    r"\bbody[\s\-]?cream\b", r"\bķermeņa[\s\-]?krēms\b",
    # Found in 220.lv's men's perfume category (2026-10-03): body spray, scrub,
    # bath oil, deodorant stick, incense burner, a costume mask
    r"\bķermeņa[\s\-]?sprej\w*", r"\bskrubis\b", r"\bbody[\s\-]?scrub\b",
    r"\bvannas[\s\-]?eļļ\w*", r"\bbath[\s\-]?oil\b", r"\bstiks\b", r"\+\s*deo\b",
    r"\bdedzinātāj\w*", r"\bmaska\b",
    # Gift sets are NOT rejected here — they are kept as card_type="gift_set".
]
_NON_PERFUME_RE = re.compile("|".join(_NON_PERFUME_PATTERNS), re.IGNORECASE)

# Markers of a gift set / multi-item package. Matched against the raw title
# (and the shop's subtitle, where it has one — makeup.lv puts
# "Komplekts (edp/100ml + edp/mini/10ml)" there).
_GIFT_SET_PATTERNS = [
    r"\bgift[\s\-]?set\b", r"\bvalue[\s\-]?set\b", r"\bset\b", r"\bminisets?\b",
    r"\bkomplekt\w*\b", r"\bdāvanu[\s\-]?(komplekt\w*|kast\w*)\b",
    r"\brinkinys\b", r"\bcoffret\b",
    r"\bподарочн\w*\s+набор\w*\b", r"\bнабор\w*\b",
    # Composition listings: "edp/100ml + edp/10ml", "75 ml + 12.5 ml" — but
    # "30 ml + Case" is one bottle with a travel case, not a set.
    r"\d+(?:[.,]\d+)?\s*ml\s*\+(?!\s*case\b)",
    # Douglas names a bottle with its travel spray "100 + 15 ml".
    r"\b\d+(?:[.,]\d+)?\s*\+\s*\d+(?:[.,]\d+)?\s*ml\b",
]
_GIFT_SET_RE = re.compile("|".join(_GIFT_SET_PATTERNS), re.IGNORECASE)


# A pack that differs from the plain bottle of the same size ("100 ml Refill",
# "100 ml Without Stand"). It must not share a (url, volume) record with the
# bottle, so it becomes part of the volume label: "100ml refill".
# "Refillable" is the ordinary bottle and is not a qualifier.
# (pattern, label, only after the volume). The last two tell apart variants of
# one product ("125 ml (ierobežota daudzuma prece)", "30 ml … + Case"), so they
# count only after the volume: a perfume whose NAME says "Limited Edition"
# keeps its plain volume.
_VOLUME_QUALIFIERS = [
    (re.compile(r"\brefill\b|\buzpilde\b", re.IGNORECASE), "refill", False),
    (re.compile(r"\bwithout stand\b|\bbez statīva\b", re.IGNORECASE), "without stand", False),
    # notino.lv: "Smaržas (ierobežota daudzuma prece)" = limited edition bottle
    (re.compile(r"\bierobežota daudzuma\b|\blimited edition\b", re.IGNORECASE), "limited edition", True),
    # notino.lv: "Tualetes ūdens (EDT) + Case" = the bottle with a travel case
    (re.compile(r"\+\s*case\b|\bwith case\b|\bceļojuma\s+futlār\w*", re.IGNORECASE), "with case", True),
]


def volume_qualifier(text: str | None) -> str | None:
    if not text:
        return None
    volume = PerfumeNormalizer.REGEX_VOLUME.search(text)
    after_volume = text[volume.end():] if volume else ""
    for pattern, label, only_after in _VOLUME_QUALIFIERS:
        if pattern.search(after_volume if only_after else text):
            return label
    return None


# Type lines that name the perfume's line instead of its type: douglas.lv sells
# "BLEU DE CHANEL" with the type line "L'EXCLUSIF". Such a label must join the
# title (it is a different perfume) and cannot go into CONC_MAP, because
# CONC_MAP labels are stripped from the name.
_LINE_NAME_CONCENTRATION = {
    "l'exclusif": "Parfum",  # Ervin: духи
}


def line_name_concentration(text: str | None) -> str | None:
    """Concentration for a type line that is a known line name, else None."""
    key = re.sub(r"\s+", " ", (text or "").replace("’", "'")).strip().lower()
    return _LINE_NAME_CONCENTRATION.get(key)


def detect_card_type(*texts: str | None) -> str:
    """Classify a listing from its raw title (+ optional subtitle):
    "gift_set" or "perfume"."""
    joined = " ".join(t for t in texts if t)
    return "gift_set" if joined and _GIFT_SET_RE.search(joined) else "perfume"


# A fragrance item inside a set's composition ("edp/100ml", "perf/75ml", "parfum").
_SET_PERFUME_ITEM_RE = re.compile(
    r"\b(edp|edt|edc|perf|parfum|perfume|eau|mini|cologne)\b|smarž|ūdens|kvepal|духи|туалетн|парфюм",
    re.IGNORECASE,
)


def is_non_perfume_set(*texts: str | None) -> bool:
    """True for a gift set whose composition is spelled out and names no
    fragrance item — aftershave lotion + shower gel, a home diffuser. A set
    with an unlisted composition ("Komplekts, 7 preces") is kept."""
    joined = " ".join(t for t in texts if t)
    return bool(re.search(r"[/+]", joined)) and not _SET_PERFUME_ITEM_RE.search(joined)


def is_non_perfume_title(title: str) -> bool:
    """Return True if the raw scraped title clearly identifies a non-perfume
    product (deodorant, body spray, shampoo, aftershave, etc.).

    Must be called on the RAW title before PerfumeNormalizer strips noise —
    once 'dezodorants' is removed from the title, the product is
    indistinguishable from a real perfume.
    """
    if not title:
        return False
    return bool(_NON_PERFUME_RE.search(title))
