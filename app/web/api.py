from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from sqlmodel import select, Session
from typing import List, Optional
from datetime import datetime

from app.core.database import async_session
from app.domain.models import ProductGroup, Product, PriceHistory, ScrapingRule
from app.services.scraper import scraper_service
from app.services.ai_generator import ai_generator
from app.main import process_target
from app.services.analyzer import price_analyzer

app = FastAPI(title="MarketPulse API", description="Intelligence Backend for Price Monitoring")

@app.get("/")
async def root():
    return {"status": "online", "message": "MarketPulse API is running"}

@app.get("/groups", response_model=List[ProductGroup])
async def get_groups():
    async with async_session() as session:
        statement = select(ProductGroup)
        result = await session.execute(statement)
        return result.scalars().all()

@app.get("/groups/{group_id}/products")
async def get_group_products(group_id: int):
    async with async_session() as session:
        statement = select(Product).where(Product.group_id == group_id)
        result = await session.execute(statement)
        products = result.scalars().all()
        return products

@app.get("/groups/{group_id}/analysis")
async def get_group_analysis(group_id: int):
    """
    Сравнительный анализ цен внутри группы (разные магазины).
    """
    async with async_session() as session:
        analysis = await price_analyzer.analyze_group(session, group_id)
        if not analysis:
            raise HTTPException(status_code=404, detail="No products found in this group")
        return analysis

@app.get("/products/{product_id}/stats")
async def get_product_stats(product_id: int):
    """
    История цен конкретного товара.
    """
    async with async_session() as session:
        stats = await price_analyzer.get_stats(session, product_id)
        return stats

@app.post("/scrape")
async def trigger_scrape(target_url: str, search_term: str, background_tasks: BackgroundTasks):
    """
    Запускает процесс парсинга в фоновом режиме.
    """
    target = {
        "url": target_url,
        "search_term": search_term,
        "category": "API Triggered"
    }
    
    async def run_scrape():
        async with async_session() as session:
            await process_target(session, target)

    background_tasks.add_task(run_scrape)
    return {"message": "Scrape task started", "target": target_url}

@app.get("/health/rules")
async def get_rules_health():
    """
    Показывает статус 'здоровья' всех правил парсинга.
    """
    async with async_session() as session:
        statement = select(ScrapingRule)
        result = await session.execute(statement)
        rules = result.scalars().all()
        return [
            {
                "domain": r.domain,
                "health_score": r.health_score,
                "success_count": r.success_count,
                "failure_count": r.failure_count,
                "last_error": r.last_error
            } for r in rules
        ]
