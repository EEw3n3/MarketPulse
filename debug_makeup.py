import asyncio
from app.core.client import stealth_client
from parsel import Selector

async def debug_makeup():
    await stealth_client.init_session()
    url = "https://makeup.lv/categorys/3218/"
    html = await stealth_client.get_page(url)
    if not html:
        print("Failed to fetch")
        return
    
    sel = Selector(text=html)
    container = "li.simple-slider-list__item[data-id]"
    items = sel.css(container)
    print(f"Container '{container}': {len(items)} items")
    
    # Check if there are other lists
    other_items = sel.css('li[data-id]')
    print(f"Total li[data-id]: {len(other_items)} items")

    await stealth_client.close()

if __name__ == "__main__":
    asyncio.run(debug_makeup())
