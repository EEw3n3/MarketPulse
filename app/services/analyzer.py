from decimal import Decimal
from typing import List, Optional
from loguru import logger
from sqlmodel import select, func
from app.domain.models import Product, PriceHistory, ProductGroup

class PriceAnalyzer:
    """
    Сервис для анализа цен и выявления аномалий.
    """
    
    @staticmethod
    async def get_stats(session, product_id: int):
        """
        Возвращает статистику по конкретному товару: мин, макс, средняя.
        """
        stmt = select(
            func.min(PriceHistory.price),
            func.max(PriceHistory.price),
            func.avg(PriceHistory.price)
        ).where(PriceHistory.product_id == product_id)
        
        result = await session.execute(stmt)
        min_p, max_p, avg_p = result.one()
        
        return {
            "min": Decimal(min_p or 0),
            "max": Decimal(max_p or 0),
            "avg": Decimal(avg_p or 0)
        }

    @staticmethod
    def detect_price_drop(current_price: Decimal, history_stats: dict, threshold: float = 0.1) -> bool:
        """
        Проверяет, является ли текущая цена выгодной (ниже средней на X%).
        """
        if not history_stats["avg"]: return False
        
        avg = history_stats["avg"]
        drop = (avg - current_price) / avg if avg > 0 else 0
        
        if drop >= Decimal(str(threshold)):
            return True
        return False

    async def analyze_group(self, session, group_id: int):
        """
        Сравнивает цены внутри группы (разные магазины).
        Находит самое выгодное предложение.
        """
        stmt = select(Product).where(Product.group_id == group_id)
        result = await session.execute(stmt)
        products = result.scalars().all()
        
        if not products: return None
        
        # Фильтруем товары с ценой > 0
        priced_products = [p for p in products if p.last_price and p.last_price > 0]
        if not priced_products: return None
        
        best_offer = min(priced_products, key=lambda p: p.last_price)
        avg_price = sum(p.last_price for p in priced_products) / len(priced_products)
        
        return {
            "group_id": group_id,
            "best_price": best_offer.last_price,
            "best_store": best_offer.search_term, # В нашем случае search_term пока хранит имя магазина из правила
            "avg_group_price": round(avg_price, 2),
            "savings": round(avg_price - best_offer.last_price, 2)
        }

price_analyzer = PriceAnalyzer()
