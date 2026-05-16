from typing import Optional, List, Literal
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field

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

class StoreOfferVariant(BaseModel):
    """One product within a store (used for popover when a store has duplicates by volume)."""
    product_id: int
    price: float
    url: str
    image_url: Optional[str] = None


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
    variants: List[StoreOfferVariant] = []


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

    # Nested data
    history: List[PriceHistoryRead] = []
    offers: List[StoreOffer] = []  # Per-store cheapest offers (max 5), with variants for duplicates

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
    created_at: datetime


class FavoriteCreate(BaseModel):
    product_id: int
    alert_enabled: bool = True


class FavoriteUpdate(BaseModel):
    alert_enabled: Optional[bool] = None


# --- Chat ---

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []

class ChatResponse(BaseModel):
    reply: str
