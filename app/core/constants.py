# app/core/constants.py

# A centralized dictionary for hardcoded scraping strings to prevent "Brittle Strings" issues.

# --- LOCALE & AVAILABILITY ---
# A set of known 'out of stock' phrases across different languages and stores.
# If a variant button contains any of these, it is flagged as NOT available.
OUT_OF_STOCK_PHRASES = {
    "nav pieejams",     # LV Notino
    "nav noliktavā",    # LV general
    "izpārdots",        # LV
    "out of stock",     # EN
    "not available",    # EN
    "sold out",         # EN
    "нет в наличии",    # RU
    "распродано",       # RU
}

# --- UNITS ---
# Supported volume and weight units to extract from text
# Used in regex: \d+\s*(ml|g|oz|l)
MEASUREMENT_UNITS = ["ml", "g", "oz", "l"]

# --- COOKIES ---
# A master list of known cookie banner buttons to aggressively click across all stores
COOKIE_ACCEPT_BUTTONS = [
    "button:has-text('Pieņemt visu')", 
    "button:has-text('Piekrītu')", 
    "button:has-text('Apstiprināt')", 
    "button:has-text('Piekrist visiem')", 
    "button:has-text('Pieņemt')", 
    "button:has-text('Accept all')",
    "button:has-text('Accept')",
    "button:has-text('Принять все')",
    "#onetrust-accept-btn-handler", 
    ".cookie-consent-accept"
]

# --- DOMAINS ---
# Domains confirmed to be stable and NOT aggressively rate-limiting.
# These get shorter delays and faster browser mode.
# NOTE: notino.lv uses Network Interceptor, so it's fast by different means.
VERIFIED_FAST_DOMAINS: set[str] = {
    "douglas.lv",
    "1a.lv",
    "220.lv",
    "notino.lv",
}

# Per-domain deep-dive concurrency limits and delay ranges (min, max) in seconds.
# Used in scrape_catalog() when scheduling deep dives.
DOMAIN_DEEP_DIVE_CONFIG: dict[str, dict] = {
    "douglas.lv": {"concurrent": 2, "delay_min": 1.5, "delay_max": 3.0},
    "notino.lv":  {"concurrent": 5, "delay_min": 0.5, "delay_max": 1.0},
    "1a.lv":      {"concurrent": 3, "delay_min": 0.5, "delay_max": 1.0},
    "220.lv":     {"concurrent": 3, "delay_min": 0.5, "delay_max": 1.0},
    "makeup.lv":  {"concurrent": 2, "delay_min": 1.0, "delay_max": 2.0},
    # Default for unknown domains (conservative)
    "_default":   {"concurrent": 3, "delay_min": 3.0, "delay_max": 5.0},
}

# --- PRODUCT FILTER ---
# Keywords that identify non-perfume items to discard entirely.
# Items whose title contains ANY of these (case-insensitive) are skipped before DB save.
PRODUCT_BLACKLIST: list[str] = [
    "dezodorant",
    # "miniatūra" intentionally absent (Ervin, 2026-10-03): a miniature is a
    # perfume; the normalizer drops the word so it joins the full-size group.
    "antiperspirant",
    "antiseptiķis",
    "difuzors",
    "želeja",
    "losjons",
    "balzams",
    "krēms",
    "aftershave",
    "after shave",
    "body lotion",
    "shower gel",
    # "komplekts" intentionally absent: gift sets are kept and typed as
    # card_type="gift_set" (see normalizer.detect_card_type).
]

# --- FALLBACK CSS SELECTORS ---
# Used when AI-generated rule selectors fail.
# Covers the most common product card patterns across generic e-commerce sites.
FALLBACK_CONTAINER_CSS: str = (
    "li.catalog-products-list__item, li.simple-slider-list__item, "
    "li.product-item, .product-item, .product-card, .item, article"
)

FALLBACK_TITLE_CSS: str = (
    ".product-details__name, .simple-slider-list__name, "
    "h3, h2, .title, a.title, .name"
)
