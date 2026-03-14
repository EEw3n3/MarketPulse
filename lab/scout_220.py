"""
Scout 220.lv via full Playwright browser execution (SPA site — JS required).
Waits for the product grid to appear before saving HTML.
"""
import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.browser import browser_manager
from parsel import Selector
from loguru import logger

# Confirmed from client-side JS references in the category shell page
URL_220 = "https://220.lv/lv/smarzas/viriesu_smarzas"
OUT_FILE = "lab/scout_220_rendered.html"

# Candidate selectors to test after rendering
CANDIDATES = {
    "container": [
        "div.catalog-taxons-product",
        "li.catalog-taxons-product",
        "[class*='catalog-taxons-product'][class*='grid']",
        "[class*='product-item']:not([class*='slider'])",
        "[class*='product-card']",
        "[class*='goods-item']",
        "[class*='c-product']",
        "article[class*='product']",
    ],
    "title": [
        "a.catalog-taxons-product__name",
        "[class*='product-name'] a",
        "a[class*='name']",
        "h3 a", "h2 a",
    ],
    "price": [
        "span.catalog-taxons-product-price__price-number",
        "[class*='price-number']",
        "[class*='current-price']",
        "[class*='new-price']",
        "[class*='PriceText']",
    ],
    "pagination": [
        "a.paginator__next",
        "a[class*='next']",
        "a[rel='next']",
    ],
}


def analyze(html: str):
    sel = Selector(text=html)
    title = sel.css('title::text').get('')
    h1 = sel.css('h1::text, h1 *::text').get('')
    print(f"\nTitle: {title!r}  |  H1: {h1!r}")
    print(f"HTML size: {len(html)} bytes\n")

    for ctype, css_list in CANDIDATES.items():
        print(f"=== {ctype.upper()} ===")
        found_any = False
        for css in css_list:
            try:
                els = sel.css(css)
                if els:
                    sample = els[0].xpath('string(.)').get()[:60].strip().replace('\n', ' ')
                    cls = els[0].attrib.get('class', '')[:60]
                    print(f"  {len(els):3d}x  {css:<45}  class='{cls}'  → '{sample}'")
                    found_any = True
            except Exception:
                pass
        if not found_any:
            print("  ❌ No candidates matched")
        print()

    # Dump all unique class names containing product/price keywords
    import re
    all_cls = {}
    for el in sel.css('[class]'):
        for c in el.attrib.get('class', '').split():
            if any(k in c.lower() for k in ['product', 'price', 'item', 'catalog', 'goods', 'card']):
                all_cls[c] = all_cls.get(c, 0) + 1
    if all_cls:
        print("=== All product/price class names ===")
        for c, n in sorted(all_cls.items(), key=lambda x: -x[1])[:30]:
            print(f"  {n:4d}x  {c}")
    else:
        print("❌ Still no product-related class names — JS did not render products")


async def main():
    logger.info(f"🌐 Browser fetch: {URL_220}")
    await browser_manager.start()

    # Use full browser with extra wait for JS to render
    resp = await browser_manager.get_page_content(URL_220, fast_mode=False)

    if not resp or not resp.get("html"):
        logger.error("Browser returned no HTML!")
        await browser_manager.stop()
        return

    html = resp["html"]
    logger.success(f"✅ Browser rendered: {len(html)} bytes")

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"💾 Saved to {OUT_FILE}")

    analyze(html)
    await browser_manager.stop()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
