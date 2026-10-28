from typing import Optional, List, Literal
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# --- Base Schemas ---

class PriceHistoryRead(BaseModel):
    id: int
    price: Decimal
    in_stock: bool
    parsed_at: datetime
    change_type: str
    # store_name identifies which store this point belongs to (for multi-line
    # PriceChart that overlays history from all stores in a ProductGroup).
    # Empty string for legacy callers that don't populate this.
    store_name: str = ""

    model_config = ConfigDict(from_attributes=True)

# --- UI Specific Schemas ---

class ProductFeedItem(BaseModel):
    """Schema for ProductFeed.tsx dashboard cards"""
    id: int
    brand: str
    title: str
    currentPrice: float
    previousPrice: float
    changePercent: float
    changeDirection: Literal["up", "down", "none"]
    storeInitial: str  # e.g., "D", "N", "M"
    storeName: str     # e.g., "Douglas.lv"
    storeColor: str    # Tailwind class e.g., "bg-blue-500"
    image_url: Optional[str] = None
    lastUpdated: str = ""  # ISO timestamp of last_seen — lets the dashboard sort "Latest changes" by recency

class CatalogItem(BaseModel):
    """Schema for CatalogContent.tsx table and grid"""
    id: int
    sku: str           # mapping from internal ID or URL hash
    brand: str
    name: str
    volume: str
    type: str          # Concentration (EDP, EDT)
    price: float
    previousPrice: float
    changePercent: float
    changeDirection: Literal["up", "down", "none"]
    store: str
    storeColor: str    # e.g., "bg-blue-500"
    in_stock: bool
    lastUpdated: str   # formatted date
    promoPrice: Optional[float] = None  # price with a shop promo code
    promoCode: Optional[str] = None

class StoreOfferVariant(BaseModel):
    """One product within a store (used for popover when a store has duplicates by volume)."""
    product_id: int
    price: float
    url: str
    image_url: Optional[str] = None
    concentration: Optional[str] = None   # EDT / EDP / Parfum — surfaced as listing label


class StoreOffer(BaseModel):
    """One store row in the Price Comparison block.
    `price` is the cheapest offer for that store at the same volume; if the store
    has multiple listings of the same volume, the rest live in `variants` and are
    revealed via a popover."""
    product_id: int                   # ID of the cheapest listing (for navigation)
    url: str                          # External URL of the cheapest listing
    storeName: str
    storeInitial: str
    storeColor: str
    price: float
    previousPrice: float
    changePercent: float
    changeDirection: Literal["up", "down", "none"]
    image_url: Optional[str] = None
    concentration: Optional[str] = None   # EDT / EDP / Parfum of the BEST listing
    variants: List[StoreOfferVariant] = []
    promoPrice: Optional[float] = None    # price with a shop promo code
    promoCode: Optional[str] = None


class ProductCardDetail(BaseModel):
    """Complete data for a single product page"""
    id: int
    url: str
    title: str
    brand: Optional[str]
    volume: Optional[str]
    concentration: Optional[str]
    image_url: Optional[str]
    description: Optional[str]
    current_price: float
    old_price: Optional[float]
    store_name: str
    is_available: bool
    promo_price: Optional[float] = None   # price with a shop promo code
    promo_code: Optional[str] = None

    # Nested data
    history: List[PriceHistoryRead] = []
    offers: List[StoreOffer] = []  # Per-store cheapest offers (max 5), with variants for duplicates

    # Redesign: name without brand/volume, the same bottle in other sizes and a
    # forward-filled daily price per shop for the chart.
    display_name: Optional[str] = None
    sizes: List["SizeOption"] = []
    series: Optional["PriceSeries"] = None


class SizeOption(BaseModel):
    product_id: int
    volume: str
    min_price: float
    shops: int


class PriceSeries(BaseModel):
    """Daily lowest price per shop. `days` are ISO dates, oldest first; every
    list in `shops` has one value per day (null = not listed / out of stock)."""
    days: List[str]
    shops: dict[str, List[Optional[float]]]
    cheapest: List[Optional[str]] = []

ProductCardDetail.model_rebuild()


# --- Catalogue cards (redesign) ---

class CardOffer(BaseModel):
    product_id: int
    store: str              # canonical key: notino, makeup, 220, douglas, 1a
    store_name: str
    title: str
    price: float
    old_price: Optional[float] = None
    promo_price: Optional[float] = None
    promo_code: Optional[str] = None
    url: str
    in_stock: bool
    checked_at: Optional[datetime] = None
    change_30d: Optional[float] = None


class CatalogCard(BaseModel):
    """One perfume in one size, with every shop that sells it."""
    key: str
    product_id: int          # cheapest offer; the product page link
    brand: str
    name: str
    concentration: Optional[str] = None
    volume: Optional[str] = None
    image_url: Optional[str] = None
    min_price: float
    max_price: float
    cheapest_store: str
    shops: int
    change_30d: Optional[float] = None
    has_promo: bool = False
    offers: List[CardOffer] = []


class CardsPage(BaseModel):
    total: int
    listings: int
    items: List[CatalogCard]


class ListingRow(BaseModel):
    product_id: int
    brand: str
    name: str
    title: str
    volume: Optional[str] = None
    concentration: Optional[str] = None
    image_url: Optional[str] = None
    price: float
    old_price: Optional[float] = None
    promo_price: Optional[float] = None
    promo_code: Optional[str] = None
    change_30d: Optional[float] = None
    store: str
    store_name: str
    in_stock: bool
    url: str
    checked_at: Optional[datetime] = None


class ListingsPage(BaseModel):
    total: int
    items: List[ListingRow]


class FacetValue(BaseModel):
    value: str
    label: str
    count: int


class CatalogFacets(BaseModel):
    stores: List[FacetValue]
    concentrations: List[FacetValue]
    volumes: List[FacetValue]
    brands: List[FacetValue]
    price_min: float
    price_max: float
    as_of: Optional[datetime] = None


# --- Market snapshot (landing teaser + Pro analytics overview) ---

class ShopSnapshot(BaseModel):
    store: str
    store_name: str
    products: int            # every priced listing ever seen
    current: int             # in stock on the latest scan
    changes_7d: int          # real price changes, synthetic gap-fill excluded
    changes_30d: int
    cheapest_share: float    # % of comparable bottles where this shop is cheapest
    cheapest_count: int
    promo_listings: int


class MarketSnapshot(BaseModel):
    as_of: Optional[datetime]
    total_products: int
    current_products: int
    comparable: int          # bottles in stock in 2+ shops
    changes_7d: int
    changes_30d: int
    history_rows: int
    history_since: Optional[datetime]
    spread_median: float     # % the dearest shop asks over the cheapest
    spread_mean: float
    shops: List[ShopSnapshot]


class MoveItem(BaseModel):
    product_id: int
    store: str
    store_name: str
    brand: str
    name: str
    concentration: Optional[str] = None
    volume: Optional[str] = None
    image_url: Optional[str] = None
    old_price: float
    new_price: float
    change_percent: float
    since: Optional[datetime] = None


class ActivityPoint(BaseModel):
    date: str
    store: str
    up: int
    down: int


class PriceIndex(BaseModel):
    days: List[str]
    shops: dict[str, List[Optional[float]]]
    basket: dict[str, int]          # listings in each shop's basket
    estimated_from: Optional[str] = None
    estimated_to: Optional[str] = None


class BrandShopCell(BaseModel):
    brand: str
    store: str
    premium: float                  # % over the cheapest shop, mean
    bottles: int


class BrandShopMatrix(BaseModel):
    brands: List[str]
    stores: List[str]
    cells: List[BrandShopCell]


class DistributionBin(BaseModel):
    lower: float
    upper: float
    count: int


class PriceBandRow(BaseModel):
    store: str
    band: int
    label: str
    count: int


class GapRow(BaseModel):
    card: CatalogCard
    gap_percent: float
    gap_eur: float
    dearest_store: str


class LandingData(BaseModel):
    market: MarketSnapshot
    hero: Optional[CatalogCard] = None
    shelf: List[CatalogCard] = []
    gaps: List[CatalogCard] = []
    drops: List[MoveItem] = []


class DashboardStats(BaseModel):
    """General KPIs for Analytics page"""
    total_products: str
    avg_price_change: str
    stores_monitored: int
    potential_savings: str
    alerts_triggered: int


# --- Analytics (B2B aggregations) ---

class MoverItem(BaseModel):
    """A single product appearing in /analytics/movers."""
    product_id: int
    brand: Optional[str]
    title: str
    image_url: Optional[str]
    store_name: str
    current_price: float
    start_price: float
    change_abs: float        # absolute € delta (signed)
    change_percent: float    # signed percent
    direction: Literal["up", "down"]


class SpreadItem(BaseModel):
    """A single ProductGroup with cross-store price spread."""
    group_id: int
    name: str
    image_url: Optional[str]
    cheapest_product_id: int
    cheapest_store: str
    cheapest_price: float
    most_expensive_store: str
    most_expensive_price: float
    spread_abs: float
    spread_percent: float
    store_count: int


class RetailerStats(BaseModel):
    """Per-retailer aggregate row."""
    store: str
    product_count: int
    avg_price: float
    drop_count: int          # products currently lower than old_price
    drop_rate: float         # drop_count / product_count, percent 0-100
    cheapest_wins: int       # # multi-store groups where this store has the lowest price
    cheapest_win_rate: float # cheapest_wins / total_multi_groups_present_in, percent


class BrandStoreCell(BaseModel):
    """One cell of the brand × store heatmap."""
    brand: str
    store: str
    product_count: int
    avg_price: float


class VolatilityItem(BaseModel):
    """A single product appearing in /analytics/volatility."""
    product_id: int
    brand: Optional[str]
    title: str
    image_url: Optional[str]
    store_name: str
    current_price: float
    volatility_eur: float    # stddev of price across observations
    range_eur: float         # max - min
    observation_count: int


class MarketTrendPoint(BaseModel):
    """One day in the catalog-wide average-price trend."""
    date: str                # ISO YYYY-MM-DD
    avg_price: float
    observation_count: int


class MoversDistributionBin(BaseModel):
    """One bin in the % change histogram."""
    lower: float             # inclusive (e.g. -30 means -30%)
    upper: float             # exclusive
    count: int
    label: str               # human-friendly e.g. "-30..-25%"


class RetailerTrendPoint(BaseModel):
    date: str                # ISO YYYY-MM-DD
    avg_price: float


class RetailerTrendSeries(BaseModel):
    """Per-retailer time series for the trend chart."""
    store: str
    points: List[RetailerTrendPoint]

# --- Domain Read Schemas (Legacy/Internal) ---

class ProductGroupRead(BaseModel):
    id: int
    name: str
    category: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Auth Schemas ---

class UserPreferencesRead(BaseModel):
    monitored_stores: List[str] = []
    interested_brands: List[str] = []
    onboarding_completed: bool = False
    notification_channels: List[str] = []
    notification_threshold_percent: float = 5.0
    telegram_chat_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UserPreferencesUpdate(BaseModel):
    """Partial update — all fields optional; only provided ones are written."""
    monitored_stores: Optional[List[str]] = None
    interested_brands: Optional[List[str]] = None
    onboarding_completed: Optional[bool] = None
    notification_channels: Optional[List[str]] = None
    notification_threshold_percent: Optional[float] = None


class TelegramConnectResponse(BaseModel):
    deep_link: str
    expires_at: datetime


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=100)


class UserRead(BaseModel):
    """User profile returned from /auth/me, /auth/register, /auth/login.
    `is_admin` is read-only — set server-side via ADMIN_EMAIL env, never by client."""
    id: int
    email: EmailStr
    full_name: Optional[str]
    is_active: bool
    is_admin: bool
    # "free" or "pro". Admins get every Pro feature regardless of this value.
    plan: str = "free"
    created_at: datetime
    preferences: Optional[UserPreferencesRead] = None

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserRead


# --- Favorites ---

class FavoriteItem(BaseModel):
    """Row in the watchlist view — product snapshot + user-specific meta."""
    id: int                       # favorite.id (not product.id)
    product_id: int
    brand: Optional[str]
    title: str
    volume: Optional[str]
    concentration: Optional[str]
    image_url: Optional[str]
    current_price: float
    previous_price: Optional[float]
    price_when_added: Optional[float]
    change_percent: float
    change_direction: Literal["up", "down", "none"]
    store_name: str
    is_available: bool
    alert_enabled: bool
    # Personal drop threshold for this bottle; None = general setting.
    alert_threshold_percent: Optional[float] = None
    created_at: datetime
    # Redesign: the same bottle in every shop (cheapest listing per shop, this
    # one included), 30 days of daily prices per shop and the cheapest line's
    # change over that window.
    display_name: Optional[str] = None
    offers: List["FavoriteOffer"] = []
    series: Optional[PriceSeries] = None
    change_30d: Optional[float] = None


class FavoriteOffer(BaseModel):
    product_id: int
    store: str
    store_name: str
    price: float
    old_price: Optional[float] = None
    url: Optional[str] = None
    is_available: bool = True


FavoriteItem.model_rebuild()


class FavoriteCreate(BaseModel):
    product_id: int
    alert_enabled: bool = True


class FavoriteUpdate(BaseModel):
    alert_enabled: Optional[bool] = None
    # Send 0 to clear the personal threshold and fall back to the general one.
    alert_threshold_percent: Optional[float] = Field(default=None, ge=0, le=90)


# --- Chat ---

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

    @field_validator("content")
    @classmethod
    def _cut_content(cls, v: str) -> str:
        # Long old answers only cost prompt tokens; keep the start.
        return v[:4000]

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    # The chat sends the last 6 messages; anything older is dropped.
    history: List[ChatMessage] = Field(default_factory=list, max_length=12)
    # Short description of the page the chat was opened on (product, filters).
    page_context: Optional[str] = Field(default=None, max_length=300)

class ChatResponse(BaseModel):
    reply: str
