from typing import Optional, List
from decimal import Decimal
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship

# --- Правила парсинга (без изменений) ---
class ScrapingRule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    domain: str = Field(unique=True, index=True)
    site_name: str = Field(default="Unknown Shop") # Название магазина (Nike, Zara...)
    emoji: str = Field(default="🛒") # Эмодзи для логов
    container_css: str
    title_css: str
    price_css: Optional[str] = Field(default=None)
    stock_css: Optional[str] = Field(default=None)
    next_page_css: Optional[str] = Field(default=None)

# --- 1. ТОВАР (Статичные данные) ---
class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    url: str = Field(unique=True, index=True) # URL теперь уникален!
    title: str
    search_term: str = Field(default="unknown", index=True) # Что искал клиент
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Связь: У товара может быть много записей истории
    history: List["PriceHistory"] = Relationship(back_populates="product")

# --- 2. ИСТОРИЯ ЦЕН (Динамические данные) ---
class PriceHistory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    price: Decimal
    in_stock: bool
    parsed_at: datetime = Field(default_factory=datetime.utcnow) # Время проверки
    
    # Связь с таблицей Product
    product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    product: Optional[Product] = Relationship(back_populates="history")