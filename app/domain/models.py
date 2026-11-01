from typing import Optional, List
from decimal import Decimal
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship, Column, JSON
from sqlalchemy import ForeignKey, Integer, UniqueConstraint

# --- 1. PRODUCT GROUP (Aggregation for comparison) ---
class ProductGroup(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True) # Example: "iPhone 15 128GB Black"
    category: Optional[str] = Field(default="General", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationship with specific offers in different stores
    products: List["Product"] = Relationship(back_populates="group")

# --- 2. PARSING RULES (Domain configuration) ---
class ScrapingRule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    domain: str = Field(unique=True, index=True)
    site_name: str = Field(default="Unknown Shop") # Store name (Nike, Zara...)
    emoji: str = Field(default="🛒")
    
    # Selectors
    container_css: str
    title_css: str
    price_css: Optional[str] = Field(default=None)
    image_css: Optional[str] = Field(default=None)
    brand_css: Optional[str] = Field(default=None) # Added for better brand accuracy
    concentration_css: Optional[str] = Field(default=None) # Latvian site CONC element (Douglas/Makeup); null for sites where CONC lives inline in title
    stock_css: Optional[str] = Field(default=None)
    next_page_css: Optional[str] = Field(default=None)
    
    # Detail Page Scraping (Deep Dive)
    use_detail_page: bool = Field(default=False)
    detail_trigger_text: Optional[str] = Field(default=None) # Keywords (comma-sep) that trigger deep dive (e.g. "sākot,from")
    detail_variant_selector: Optional[str] = Field(default=None) # CSS for the container of each variant
    detail_variant_name_css: Optional[str] = Field(default=None) # CSS for the name of the variant (e.g. 50ml)
    detail_variant_price_css: Optional[str] = Field(default=None) # CSS for the price of the specific variant

    # Contextual filter
    negative_keywords: Optional[str] = Field(default="[]") # JSON list of strings
    
    # Health metrics (autonomy)
    last_success: Optional[datetime] = Field(default=None)
    last_error: Optional[str] = Field(default=None)
    success_count: int = Field(default=0)
    failure_count: int = Field(default=0)
    health_score: float = Field(default=1.0) # 0.0 - 1.0

    def __repr__(self) -> str:
        return f"<ScrapingRule domain='{self.domain}' site='{self.site_name}' health={self.health_score}>"

    # Resume capability (Checkpoints)
    last_page_url: Optional[str] = Field(default=None)
    items_scraped_current_run: int = Field(default=0)


# --- 3. PRODUCT (Specific offer in store) ---
class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    url: str = Field(index=True)
    title: str
    image_url: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    
    search_term: str = Field(default="unknown", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # --- Normalization (for Perfume Chains) ---
    brand: Optional[str] = Field(default=None, index=True)
    volume: Optional[str] = Field(default=None, index=True) 
    concentration: Optional[str] = Field(default=None, index=True)
    # "perfume" (regular bottle, single or multi-volume card) or "gift_set".
    # Gift sets get no ProductGroup, so they never enter price comparisons.
    card_type: str = Field(default="perfume", index=True)
    is_available: bool = Field(default=True)
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    
    # Denormalization for fast access
    last_price: Optional[Decimal] = Field(default=None)
    old_price: Optional[Decimal] = Field(default=None) # For discount tracking
    # Price with a shop promo code (notino.lv "ar kodu …"), shown next to the
    # regular price. last_price stays the price without a code.
    promo_price: Optional[Decimal] = Field(default=None)
    promo_code: Optional[str] = Field(default=None)
    # The shop's own product page, read after the catalogue pass: when and at
    # what price. A deal is shown only when the page confirmed today's price
    # (app/services/page_check.py).
    page_checked_at: Optional[datetime] = Field(default=None)
    page_price: Optional[Decimal] = Field(default=None)

    # Relationship with group (price comparison)
    group_id: Optional[int] = Field(default=None, foreign_key="productgroup.id")
    group: Optional[ProductGroup] = Relationship(back_populates="products")
    
    # Price history
    history: List["PriceHistory"] = Relationship(back_populates="product")

    def __repr__(self) -> str:
        return f"<Product title='{self.title[:30]}...' price={self.last_price} €>"

# --- 4. PRICE HISTORY (Timeseries) ---
class PriceHistory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    price: Decimal
    in_stock: bool
    parsed_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Change tracking
    # initial, price_up, price_down, no_change, back_in_stock, out_of_stock
    change_type: str = Field(default="initial") 
    
    product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    product: Optional[Product] = Relationship(back_populates="history")

# --- 4b. SCRAPE RUN (one pass over a shop's catalogue) ---
class ScrapeRun(SQLModel, table=True):
    """One pass over a shop's catalogue, on the server or by the PC worker.

    A product a shop no longer lists is never visited again, so nothing would
    ever mark it sold out. The runs give "not listed any more" a meaning: a
    product missing from two complete runs in a row is marked unavailable
    (app/services/freshness.py). A run is complete when it finished without an
    error and saw at least 90% of what a usual run of that shop sees.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    shop: str = Field(index=True, max_length=64)        # "notino.lv", same as Product.search_term
    source: str = Field(default="server", max_length=16)  # "server" | "worker"
    job_id: Optional[str] = Field(default=None, index=True, max_length=64)
    started_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    finished_at: Optional[datetime] = Field(default=None)
    status: str = Field(default="running", max_length=16)  # running | done | failed
    items_seen: int = Field(default=0)
    complete: bool = Field(default=False)
    swept: int = Field(default=0)
    note: Optional[str] = Field(default=None, max_length=255)


# --- 4c. PAGE CHECK (a listing compared with the shop's product page) ---
class PageCheck(SQLModel, table=True):
    """One listing read again on the shop's product page after a pass: every
    deal before it is shown, and a few random listings a day as an audit.
    `ok` = the catalogue's price and stock matched the page; when they did
    not, the listing was corrected to the page."""
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: Optional[int] = Field(default=None, foreign_key="product.id", index=True)
    shop: str = Field(index=True, max_length=64)
    kind: str = Field(default="deal", max_length=16)  # deal | random
    checked_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    db_price: Optional[Decimal] = Field(default=None)
    page_price: Optional[Decimal] = Field(default=None)
    db_in_stock: Optional[bool] = Field(default=None)
    page_in_stock: Optional[bool] = Field(default=None)
    ok: Optional[bool] = Field(default=None)  # None = the page could not be read
    note: Optional[str] = Field(default=None, max_length=255)


# --- 5. GLOBAL PATTERNS (System experience) ---
class SharedPattern(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    pattern_type: str = Field(index=True) # 'container', 'title', 'price', 'image', 'next_page'
    css_selector: str = Field(unique=True)
    success_count: int = Field(default=1)
    last_used: datetime = Field(default_factory=datetime.utcnow)


# --- 6. USER (Auth) ---
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=255)
    full_name: Optional[str] = Field(default=None, max_length=100)
    hashed_password: str
    is_active: bool = Field(default=True)
    is_admin: bool = Field(default=False)
    # "free" or "pro". Pro opens the analytics cabinet and data exports; an
    # admin switches it on by hand until card payments are wired in.
    plan: str = Field(default="free", max_length=16)
    # End of Pro (UTC); None with plan "pro" = no end. Pro is active while
    # plan == "pro" and this is in the future (app/services/plans.py).
    pro_until: Optional[datetime] = Field(default=None)
    # Who gave Pro: "admin" or "payment" (a paid subscription, later).
    pro_source: Optional[str] = Field(default=None, max_length=16)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# --- 6b. PLAN CHANGE (log of every Pro grant, extension, revoke, expiry) ---
class PlanChange(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False))
    at: datetime = Field(default_factory=datetime.utcnow)
    # The admin who made the change; None = the system (expiry, payment).
    by_user_id: Optional[int] = Field(default=None)
    action: str = Field(max_length=16)  # grant | extend | revoke | expire
    plan: str = Field(max_length=16)    # plan after the change
    pro_until: Optional[datetime] = Field(default=None)
    source: Optional[str] = Field(default=None, max_length=16)
    note: Optional[str] = Field(default=None, max_length=255)


# --- 7. USER PREFERENCES (Onboarding + personalization) ---
class UserPreferences(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)
    monitored_stores: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    interested_brands: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    onboarding_completed: bool = Field(default=False)

    # Notification channels — Phase 4
    notification_channels: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    notification_threshold_percent: Decimal = Field(default=Decimal("5.0"))
    telegram_chat_id: Optional[str] = Field(default=None, max_length=64)
    # One-time token for deep-link verification — cleared after successful /start
    telegram_link_token: Optional[str] = Field(default=None, max_length=64)
    telegram_link_token_expires_at: Optional[datetime] = Field(default=None)


# --- 8. FAVORITE (User watchlist entry) ---
class Favorite(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_favorite_user_product"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    alert_enabled: bool = Field(default=True)
    # Drop (in %) that triggers an alert for this bottle; None = the user's
    # general notification_threshold_percent.
    alert_threshold_percent: Optional[Decimal] = Field(default=None)
    price_when_added: Optional[Decimal] = Field(default=None)  # snapshot for "savings vs. entry"
    created_at: datetime = Field(default_factory=datetime.utcnow)
