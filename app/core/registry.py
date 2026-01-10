import os
from urllib.parse import urlparse

def register_domain(url: str):
    """
    Добавляет уникальный домен в файл scraped_domains.txt
    """
    domain = urlparse(url).netloc.replace("www.", "")
    if not domain:
        return
        
    file_path = "scraped_domains.txt"
    
    # Читаем существующие домены, чтобы избежать дублей
    existing_domains = set()
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            existing_domains = {line.strip() for line in f if line.strip()}
            
    if domain not in existing_domains:
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"{domain}\n")
        from loguru import logger
        logger.info(f"📝 Домен {domain} добавлен в реестр сайтов.")
