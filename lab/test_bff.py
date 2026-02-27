import asyncio
import json
import time
from loguru import logger
import sys
import os

# Сразу стучимся через curl_cffi, чтобы нас не забанил Cloudflare
from curl_cffi.requests import AsyncSession

async def test_notino_bff():
    # Мы знаем URL трекера (собрано из Network)
    # Это API, которое LuigisBox (используемый Notino) предоставляет для трекинга
    url = "https://collector-lv.notino.luigisbox.com/events"
    
    # Вот этот код мы вытащили из HTML каталога (`product_code`)
    target_variant_code = "NARBLNM_AEDP10" # 100ml variant Narciso Rodriguez
    
    # Подготовим Payload, имитирующий то, что шлет браузер.
    # Большинство полей (session_id, browser_id) можно генерировать случайно или харкдкодить, 
    # API часто съедает мусор, если нет жесткой проверки (что редкость для аналитики).
    import uuid
    fake_session = str(uuid.uuid4())
    fake_browser = str(uuid.uuid4())
    current_time_ms = int(time.time() * 1000)

    # Точный JSON Payload, который мы перехватили (слегка очищенный от лишнего мусора)
    payload = {
        "events": [
            {
                "stream": "clickstream",
                "type": "pageview.product",
                "data": {
                    "unified_name": f"product-{target_variant_code}"
                },
                "metadata": {
                    "version": "2.0",
                    "timestamp": current_time_ms,
                    "platform": {
                        "environment": "production",
                        "currency": "EUR",
                        "language": "lv",
                        "sales_unit": "LV",
                        "type": "web"
                    },
                    "browser_id": fake_browser,
                    "session_id": fake_session,
                    "location": {
                        "hostname": "www.notino.lv",
                        "pathname": "/", # Главное, что мы на Notino
                        "search": ""
                    },
                    # Самое важное поле, которое триггерит LuigisBox отдать детальную инфу
                    "related_to": {
                        "product_code": target_variant_code
                    }
                }
            }
        ]
    }

    # Имитируем абсолютно легитимный браузер через заголовки
    headers = {
        "accept": "application/json",
        "accept-language": "lv,en-US;q=0.9,en;q=0.8,ru;q=0.7",
        "content-type": "application/json",
        "origin": "https://www.notino.lv",
        "referer": "https://www.notino.lv/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    }

    logger.info(f"🚀 Sending direct BFF request for: {target_variant_code}")
    start_time = time.time()
    
    try:
        # Используем impersonate="chrome110" для идеального TLS Fingerprint
        async with AsyncSession(impersonate="chrome110") as session:
            response = await session.post(url, headers=headers, json=payload, timeout=10)
            
            elapsed = time.time() - start_time
            logger.info(f"⏱️ Request took {elapsed:.3f} seconds. Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    logger.success("🎯 BAM! Received Payload:")
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                    
                    # Пробуем разобрать структуру, как мы видели в твоем дампе
                    events = data.get("events", [])
                    if events:
                        event_data = events[0].get("data", {})
                        products = event_data.get("products", [])
                        if products:
                            p = products[0]
                            logger.success("✅ EXTRACTED DATA (No Browser Needed):")
                            logger.info(f"Product: {p.get('product_name')}")
                            logger.info(f"Full Price: {p.get('full_price')} EUR")
                            logger.info(f"Discount Price: {p.get('discount_price')} EUR")
                            logger.info(f"Available: {p.get('availability')}")
                        else:
                            logger.warning("No 'products' array found in response data. They might require exact cookie/session matching.")
                except Exception as e:
                    logger.error(f"Failed to parse JSON response: {e}")
                    print(response.text)
            else:
                logger.error(f"Failed with status: {response.status_code} | Body: {response.text}")
                
    except Exception as e:
         logger.error(f"Request failed entirely: {e}")

if __name__ == "__main__":
    asyncio.run(test_notino_bff())
