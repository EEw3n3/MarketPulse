from typing import Optional, List, Literal
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

# --- Base Schemas ---

class PriceHistoryRead(BaseModel):
    id: int
    price: Decimal
    in_stock: bool
    parsed_at: datetime
    change_type: str
    
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
    competitors: List["ProductFeedItem"] = []  # Other offers in same ProductGroup

class DashboardStats(BaseModel):
    """General KPIs for Analytics page"""
    total_products: str
    avg_price_change: str
    stores_monitored: int
    potential_savings: str
    alerts_triggered: int

# --- Domain Read Schemas (Legacy/Internal) ---

class ProductGroupRead(BaseModel):
    id: int
    name: str
    category: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
