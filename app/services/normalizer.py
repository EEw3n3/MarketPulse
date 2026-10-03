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
        "Burberry", "Gisada", "Clive Christian", "BellaVita", "Afnan",
        "Jacques Zolty", "Arabiyat Prestige", "Maison Alhambra", "Bugatti",
        "Cristiano Ronaldo", "Antonio Banderas", "Banderas",
        "Davidoff", "Adidas", "Hermès", "Boucheron", "Van Cleef & Arpels",
        "La Rive", "Ungaro", "Emanuel Ungaro", "Cerruti", "Nino Cerruti",
        "BI-ES", "Jacques Bogart", "Nikos", "Bruno Banani", "Jesus Del Pozo",
        "Moncler", "Mercedes-Benz", "18.21. Man Made", "Chabaud",
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
        r"\bvīriešiem\b", r"\bmen\b", r"\bhomme\b", r"\bfor men\b",
        r"\bpour\b", r"\bfor\b", r"\bwoman\b", r"\bfemale\b", r"\bsievietēm\b",
        r"\bprocentai\b",
        # NOTE: 'intense' / 'intensive' INTENTIONALLY removed from NOISE.
        # Words like "Intense" are PRODUCT-LINE distinguishers — "Dior Sauvage"
        # and "Dior Sauvage Intense" are entirely different perfumes, but
        # stripping the word made them chain into one group. Same with
        # "Le Male" vs "Le Male Intense", etc.
        r"\bset\b", r"\bkomplekts\b",
        r"\bafter shave\b", r"\baftershave\b", r"\btester\b", r"\btestieris\b",
        r"\bparfums\b", r"\bman\b", r"\bwomen\b", r"\bwoman\b", r"\bmen\b",
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

    # "mini" marks a miniature only on a small bottle ("Vetiver Musc mini 10 ml",
    # "Dear Barber mini 30 ml"); in "Immortal Mini 150 ml" or "Pride Collection
    # Mini 01" it is the name.
    MINI_MAX_ML = 30
    REGEX_MINI = re.compile(r'\bmini\b', re.IGNORECASE)

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
        
        # 4. Concentration
        # Priority: specific EDT/EDP/EDC markers first; generic "Parfum"/"Smaržas"
        # last (they're fallback labels that should lose to explicit EDT/EDP in the same title).
        concentration = None
        sorted_conc_keys = sorted(
            PerfumeNormalizer.CONC_MAP.keys(),
            key=lambda k: (PerfumeNormalizer.CONC_MAP[k] == "Parfum", -len(k))
        )
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
        if PerfumeNormalizer.is_mini_volume(volume):
            clean_name = PerfumeNormalizer.REGEX_MINI.sub("", clean_name)

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
            # Re-apply the full NOISE list — fallback must not let Latvian noise
            # (Smaržas / vīriešiem / aerosols / uzpildīšānas …) slip back in
            # just because _before_noise preserved it.
            for _noise_pat in PerfumeNormalizer.NOISE:
                _fallback = re.sub(_noise_pat, " ", _fallback, flags=re.IGNORECASE)
            if PerfumeNormalizer.is_mini_volume(volume):
                _fallback = PerfumeNormalizer.REGEX_MINI.sub(" ", _fallback)
            # Only strip truly useless words — keep 'pour homme', 'man', 'intense', etc.
            _min_filter = {"eau", "parfum", "edt", "edp", "de", "set"}
            _fallback = " ".join(w for w in _fallback.split() if w.lower().strip("-,.") not in _min_filter)
            _fallback = _fallback.strip("-–—,. |/")
            if len(_fallback) > 2:
                clean_name = _fallback

        # If clean_name is too short or just common words, it's garbage
        if len(clean_name) <= 2:
            clean_name = ""

        # Remove orphan hyphens/dashes/commas/pipes ("Dear Barber – Eau de Toilette – …")
        clean_name = re.sub(r'^[,\-–—\|\s]+|[,\-–—\|\s]+$', '', clean_name)
        # Final cleanup for punctuation artifacts (e.g. "Name - ")
        clean_name = clean_name.strip("-–—,. |/")

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
