from loguru import logger
from typing import List
from app.domain.models import Product, PriceHistory

class NotificationService:
    """
    Analyzes differences between scans and notifies about important events.
    Supports Price Changes, New Products, and Stock updates.
    """

    def report_change(self, product: Product, history: PriceHistory, site_name: str):
        """
        Logs a human-readable message about a specific product change.
        """
        emoji = "🔔"
        msg = ""

        if history.change_type == "initial":
            emoji = "🆕"
            msg = f"New product added on {site_name}: {product.title} - {history.price}€"
        
        elif history.change_type == "price_down":
            emoji = "📉"
            diff = product.old_price - history.price
            msg = f"DISCOUNT on {site_name}! {product.title}: {product.old_price}€ -> {history.price}€ (Saved {diff}€)"
        
        elif history.change_type == "price_up":
            emoji = "📈"
            msg = f"Price increased on {site_name}: {product.title}: {product.old_price}€ -> {history.price}€"
        
        elif history.change_type == "back_in_stock":
            emoji = "✅"
            msg = f"Back in stock on {site_name}: {product.title} at {history.price}€"
        
        elif history.change_type == "out_of_stock":
            emoji = "❌"
            msg = f"Out of stock on {site_name}: {product.title}"

        if msg:
            # We use a special level or just highlight it for the user
            logger.opt(colors=True).info(f"<cyan>{emoji} [SIGNAL]</cyan> {msg}")

    def generate_scan_summary(self, session, site_name: str):
        """
        Optional: Can generate a summary report after a full site scan.
        """
        pass

notification_service = NotificationService()
