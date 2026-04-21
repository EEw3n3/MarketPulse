from typing import Optional, List
from decimal import Decimal
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship, Column, JSON

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
    is_available: bool = Field(default=True)
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    
    # Denormalization for fast access
    last_price: Optional[Decimal] = Field(default=None)
    old_price: Optional[Decimal] = Field(default=None) # For discount tracking
    
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
    created_at: datetime = Field(default_factory=datetime.utcnow)


# --- 7. USER PREFERENCES (Onboarding + personalization) ---
class UserPreferences(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)
    monitored_stores: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    interested_brands: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    onboarding_completed: bool = Field(default=False)
