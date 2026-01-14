import asyncio
import json
import sys
from app.core.client import stealth_client
from app.core.proxy import proxy_manager
from loguru import logger

async def test_identity():
    # Using professional fingerprint checking tool from Scrapfly
    test_url = "https://tools.scrapfly.io/api/fp/ja3"
    
    logger.info("🕵️‍♂️ Starting camouflage check (Tier 1)...")
    
    # Requesting via our Stealth Client
    # If proxies are dead, this method returns None after all attempts
    json_response = await stealth_client.get_page(test_url)
    
    # 1. SUCCESS response processing block (if proxies alive)
    if json_response:
        try:
            data = json.loads(json_response)
            
            print("\n" + "="*50)
            print("🔍 RESULTS (Scrapfly Fingerprint Analysis)")
            print("="*50)
            
            ja3 = data.get('ja3')
            print(f"✅ JA3 Hash: {ja3[:30]}... (truncated)")
            print(f"✅ HTTP/2 Support: {data.get('h2', False)}")
            
            if ja3:
                logger.success("🚀 TEST PASSED! We look like a legitimate browser.")
            else:
                logger.error("❌ JA3 not found. Something went wrong.")
            
            print("="*50 + "\n")
            
        except Exception as e:
            logger.error(f"Error reading response: {e}")
            print(f"Raw response: {json_response[:200]}")

    # 2. STATISTICS Block (Always executed, even if error)
    print("\n" + "-"*40)
    print("📊 PROXY MANAGER FINAL STATISTICS")
    print("-"*40)
    stats = proxy_manager.get_stats()
    print(f"Total proxies: {stats['Total']}")
    print(f"Alive:       {stats['Active']}")
    print(f"Banned:      {stats['Banned']}")
    print(f"Ban list: {stats['Banned_List']}")
    print("-"*40 + "\n")

if __name__ == "__main__":
    # FIXING WINDOWS ERROR (Proactor Event Loop)
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(test_identity())