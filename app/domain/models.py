from typing import Optional, List
from decimal import Decimal
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship

# --- 1. ГРУППА ТОВАРОВ (Агрегация для сравнения) ---
class ProductGroup(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True) # Например: "iPhone 15 128GB Black"
    category: Optional[str] = Field(default="General", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Связь с конкретными предложениями в разных магазинах
    products: List["Product"] = Relationship(back_populates="group")

# --- 2. ПРАВИЛА ПАРСИНГА (Конфигурация домена) ---
class ScrapingRule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    domain: str = Field(unique=True, index=True)
    site_name: str = Field(default="Unknown Shop") # Название магазина (Nike, Zara...)
    emoji: str = Field(default="🛒")
    
    # Селекторы
    container_css: str
    title_css: str
    price_css: Optional[str] = Field(default=None)
    image_css: Optional[str] = Field(default=None) # НОВОЕ: Для картинок
    stock_css: Optional[str] = Field(default=None)
    next_page_css: Optional[str] = Field(default=None)

    # Контекстный фильтр
    negative_keywords: Optional[str] = Field(default="[]") # JSON list of strings
    
    # Метрики здоровья (автономность)
    last_success: Optional[datetime] = Field(default=None)
    last_error: Optional[str] = Field(default=None)
    success_count: int = Field(default=0)
    failure_count: int = Field(default=0)
    health_score: float = Field(default=1.0) # 0.0 - 1.0


# --- 3. ТОВАР (Конкретное предложение в магазине) ---
class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    url: str = Field(unique=True, index=True)
    title: str
    image_url: Optional[str] = Field(default=None) # Ссылка на картинку
    description: Optional[str] = Field(default=None)
    
    search_term: str = Field(default="unknown", index=True) # Ключевое слово поиска
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Денормализация для быстрого доступа
    last_price: Optional[Decimal] = Field(default=None)
    
    # Связь с группой (сравнение цен)
    group_id: Optional[int] = Field(default=None, foreign_key="productgroup.id")
    group: Optional[ProductGroup] = Relationship(back_populates="products")
    
    # История цен
    history: List["PriceHistory"] = Relationship(back_populates="product")

# --- 4. ИСТОРИЯ ЦЕН (Таймсерии) ---
class PriceHistory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    price: Decimal
    in_stock: bool
    parsed_at: datetime = Field(default_factory=datetime.utcnow)
    
    product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    product: Optional[Product] = Relationship(back_populates="history")

# --- 5. ГЛОБАЛЬНЫЕ ПАТТЕРНЫ (Опыт системы) ---
class SharedPattern(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    pattern_type: str = Field(index=True) # 'container', 'title', 'price', 'image', 'next_page'
    css_selector: str = Field(unique=True)
    success_count: int = Field(default=1)
    last_used: datetime = Field(default_factory=datetime.utcnow)
