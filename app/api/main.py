from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc, or_
from sqlalchemy.orm import selectinload
import uvicorn

from app.api.deps import get_db
from app.api import schemas
from app.domain.models import ProductGroup, Product, PriceHistory

app = FastAPI(
    title="MarketPulse API",
    description="Backend API for MarketPulse Price Monitoring System",
    version="1.0.0",
    servers=[
        {"url": "http://46.101.174.12:8000", "description": "Production Server"},
        {"url": "http://localhost:8000", "description": "Local Development"}
    ]
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Helper Functions ---

def get_store_initial(store_name: str) -> str:
    mapping = {
        "douglas.lv": "D",
        "notino.lv": "N",
        "makeup.lv": "M",
        "1a.lv": "1",
        "220.lv": "2"
    }
    return mapping.get(store_name.lower(), "?")

def get_store_color(store_name: str) -> str:
    mapping = {
        "douglas.lv": "bg-blue-500",
        "notino.lv": "bg-[hsl(var(--success))]",
        "makeup.lv": "bg-pink-500",
        "1a.lv": "bg-orange-500",
        "220.lv": "bg-amber-500"
    }
    return mapping.get(store_name.lower(), "bg-gray-500")

# --- API Endpoints ---

@app.get("/")
async def root():
    return {"message": "Welcome to MarketPulse API", "status": "online"}

@app.get("/api/products/feed", response_model=List[schemas.ProductFeedItem])
async def get_product_feed(limit: int = 20, db: AsyncSession = Depends(get_db)):
    """Latest price changes for the dashboard feed."""
    # Fetch products that had a price change recently
    stmt = (
        select(Product)
        .where(Product.old_price.isnot(None))
        .order_by(desc(Product.last_seen))
        .limit(limit)
    )
    result = await db.execute(stmt)
    products = result.scalars().all()
    
    feed_items = []
    for p in products:
        diff = float(p.last_price - p.old_price) if p.old_price else 0
        direction = "none"
        if diff > 0: direction = "up"
        elif diff < 0: direction = "down"
        
        percent = abs(diff / float(p.old_price)) * 100 if p.old_price and p.old_price != 0 else 0
        
        feed_items.append(schemas.ProductFeedItem(
            id=p.id,
            brand=p.brand or "Unknown",
            title=p.title,
            currentPrice=float(p.last_price),
            previousPrice=float(p.old_price) if p.old_price else float(p.last_price),
            changePercent=round(percent, 1),
            changeDirection=direction,
            storeInitial=get_store_initial(p.search_term),
            storeName=p.search_term.capitalize(),
            image_url=p.image_url
        ))
    return feed_items

@app.get("/api/products/catalog", response_model=List[schemas.CatalogItem])
async def get_catalog(
    search: Optional[str] = None,
    brands: List[str] = Query(None),
    stores: List[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Full catalog with filtering and search."""
    stmt = select(Product)
    
    if search:
        stmt = stmt.where(or_(Product.title.ilike(f"%{search}%"), Product.brand.ilike(f"%{search}%")))
    if brands:
        stmt = stmt.where(Product.brand.in_(brands))
    if stores:
        stmt = stmt.where(Product.search_term.in_(stores))
        
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    products = result.scalars().all()
    
    catalog_items = []
    for p in products:
        diff = float(p.last_price - p.old_price) if p.old_price else 0
        direction = "none"
        if diff > 0: direction = "up"
        elif diff < 0: direction = "down"
        
        percent = abs(diff / float(p.old_price)) * 100 if p.old_price and p.old_price != 0 else 0
        
        catalog_items.append(schemas.CatalogItem(
            id=p.id,
            sku=f"MP-{p.id}",
            brand=p.brand or "Unknown",
            name=p.title,
            volume=p.volume or "N/A",
            type=p.concentration or "EDT",
            price=float(p.last_price),
            previousPrice=float(p.old_price) if p.old_price else float(p.last_price),
            changePercent=round(percent, 1),
            changeDirection=direction,
            store=p.search_term.capitalize(),
            storeColor=get_store_color(p.search_term),
            in_stock=p.is_available,
            lastUpdated=p.last_seen.strftime("%Y-%m-%d")
        ))
    return catalog_items

@app.get("/api/products/{product_id}", response_model=schemas.ProductCardDetail)
async def get_product_detail(product_id: int, db: AsyncSession = Depends(get_db)):
    """Detail view for a single product with history and competitors."""
    stmt = (
        select(Product)
        .options(selectinload(Product.history))
        .where(Product.id == product_id)
    )
    result = await db.execute(stmt)
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
        
    # Get competitors (other products in the same group)
    competitors = []
    if product.group_id:
        comp_stmt = select(Product).where(Product.group_id == product.group_id, Product.id != product.id)
        comp_res = await db.execute(comp_stmt)
        for cp in comp_res.scalars().all():
            competitors.append(schemas.ProductFeedItem(
                id=cp.id, brand=cp.brand or "", title=cp.title,
                currentPrice=float(cp.last_price), previousPrice=float(cp.old_price or cp.last_price),
                changePercent=0, changeDirection="none",
                storeInitial=get_store_initial(cp.search_term), storeName=cp.search_term.capitalize(),
                image_url=cp.image_url
            ))
            
    return schemas.ProductCardDetail(
        id=product.id,
        url=product.url,
        title=product.title,
        brand=product.brand,
        volume=product.volume,
        concentration=product.concentration,
        image_url=product.image_url,
        description=product.description,
        current_price=float(product.last_price),
        old_price=float(product.old_price) if product.old_price else None,
        store_name=product.search_term.capitalize(),
        is_available=product.is_available,
        history=[schemas.PriceHistoryRead.model_validate(h) for h in product.history],
        competitors=competitors
    )

@app.get("/api/analytics/stats", response_model=schemas.DashboardStats)
async def get_analytics_stats(db: AsyncSession = Depends(get_db)):
    """KPIs for the analytics page."""
    total_products = await db.scalar(select(func.count(Product.id)))
    stores_count = await db.scalar(select(func.count(func.distinct(Product.search_term))))
    
    # Simple mockup for other stats until we have more history
    return schemas.DashboardStats(
        total_products=f"{total_products:,}",
        avg_price_change="-2.4%",
        stores_monitored=stores_count or 0,
        potential_savings="€1,240",
        alerts_triggered=12
    )

if __name__ == "__main__":
    uvicorn.run("app.api.main:app", host="0.0.0.0", port=8000, reload=True)
