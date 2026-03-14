import asyncio
import os
import sys
from decimal import Decimal

# Ensure root is in path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from app.services.scraper import scraper_service
from app.domain.models import ScrapingRule

async def test_notino():
    # 1. Test Single Volume (Lattafa Eclaire)
    url_eclaire = "https://www.notino.lv/lattafa/eclaire-smarzudens-edp-abiem-dzimumiem/"
    rule = ScrapingRule(domain="notino.lv", site_name="Notino")
    
    print(f"\n--- Testing Lattafa Eclaire (Single Volume) ---")
    variants = await scraper_service.scrape_product_details(url_eclaire, rule)
    for v in variants:
        print(f"Vol: {v['title_suffix']} | Price: {v['price']} | Avail: {v['is_available']}")

    # 2. Test Multiple Variants (Scandal Elixir)
    url_scandal = "https://www.notino.lv/jean-paul-gaultier/scandal-pour-homme-elixir-smarzas-viriesiem/"
    print(f"\n--- Testing Scandal Elixir (Multiple Variants) ---")
    variants = await scraper_service.scrape_product_details(url_scandal, rule)
    for v in variants:
        print(f"Vol: {v['title_suffix']} | Price: {v['price']} | Avail: {v['is_available']}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(test_notino())
