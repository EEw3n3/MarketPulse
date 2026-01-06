import asyncio
import json
import sys
from app.core.client import stealth_client
from app.core.proxy import proxy_manager
from loguru import logger

async def test_identity():
    # Используем профессиональный инструмент для проверки отпечатков от Scrapfly
    test_url = "https://tools.scrapfly.io/api/fp/ja3"
    
    logger.info("🕵️‍♂️ Запуск проверки маскировки (Tier 1)...")
    
    # Делаем запрос через наш Stealth Client
    # Если прокси мертвые, этот метод вернет None после всех попыток
    json_response = await stealth_client.get_page(test_url)
    
    # 1. Блок обработки УСПЕШНОГО ответа (если прокси живы)
    if json_response:
        try:
            data = json.loads(json_response)
            
            print("\n" + "="*50)
            print("🔍 РЕЗУЛЬТАТЫ (Scrapfly Fingerprint Analysis)")
            print("="*50)
            
            ja3 = data.get('ja3')
            print(f"✅ JA3 Hash: {ja3[:30]}... (обрезан)")
            print(f"✅ HTTP/2 Support: {data.get('h2', False)}")
            
            if ja3:
                logger.success("🚀 ТЕСТ ПРОЙДЕН! Мы выглядим как легитимный браузер.")
            else:
                logger.error("❌ JA3 не найден. Что-то пошло не так.")
            
            print("="*50 + "\n")
            
        except Exception as e:
            logger.error(f"Ошибка чтения ответа: {e}")
            print(f"Сырой ответ: {json_response[:200]}")

    # 2. Блок СТАТИСТИКИ (Выполняется ВСЕГДА, даже если была ошибка)
    print("\n" + "-"*40)
    print("📊 ИТОГОВАЯ СТАТИСТИКА PROXY MANAGER")
    print("-"*40)
    stats = proxy_manager.get_stats()
    print(f"Всего прокси: {stats['Total']}")
    print(f"Живых:       {stats['Active']}")
    print(f"В бане:      {stats['Banned']}")
    print(f"Список бана: {stats['Banned_List']}")
    print("-"*40 + "\n")

if __name__ == "__main__":
    # ЛЕЧИМ ОШИБКУ WINDOWS (Proactor Event Loop)
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(test_identity())