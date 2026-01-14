from decimal import Decimal
from typing import List, Optional
from loguru import logger
from sqlmodel import select, func
from app.domain.models import Product, PriceHistory, ProductGroup

class PriceAnalyzer:
    """
    Service for price analysis and anomaly detection.
    """
    
    @staticmethod
    async def get_stats(session, product_id: int):
        """
        Returns statistics for a specific product: min, max, avg.
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
        Checks if current price is a bargain (below average by X%).
        """
        if not history_stats["avg"]: return False
        
        avg = history_stats["avg"]
        drop = (avg - current_price) / avg if avg > 0 else 0
        
        if drop >= Decimal(str(threshold)):
            return True
        return False

    async def analyze_group(self, session, group_id: int):
        """
        Compares prices within the group (different stores).
        Finds the best offer.
        """
        stmt = select(Product).where(Product.group_id == group_id)
        result = await session.execute(stmt)
        products = result.scalars().all()
        
        if not products: return None
        
        # Filter products with price > 0
        priced_products = [p for p in products if p.last_price and p.last_price > 0]
        if not priced_products: return None
        
        best_offer = min(priced_products, key=lambda p: p.last_price)
        avg_price = sum(p.last_price for p in priced_products) / len(priced_products)
        
        return {
            "group_id": group_id,
            "best_price": best_offer.last_price,
            "best_store": best_offer.search_term, # In our case search_term currently holds store name from rule
            "avg_group_price": round(avg_price, 2),
            "savings": round(avg_price - best_offer.last_price, 2)
        }

price_analyzer = PriceAnalyzer()
