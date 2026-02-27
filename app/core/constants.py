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
