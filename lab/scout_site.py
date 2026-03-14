"""
Lab Scout: Fetches HTML from 1a.lv and 220.lv, saves to disk, then analyzes
key structural elements to find correct CSS selectors.

Usage:
    python lab/scout_site.py 1a
    python lab/scout_site.py 220
"""
import asyncio
import sys
import os
import re
from bs4 import BeautifulSoup

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.browser import browser_manager
from app.core.client import stealth_client
from loguru import logger

TARGETS = {
    "1a": {
        "url": "https://www.1a.lv/c/smarzas-un-kosmetika/viriesu-smarzas/viriesu-smarzas/30j",
        "html_out": "lab/scout_1a.html",
    },
    "220": {
        "url": "https://www.220.lv/lv/parfumerija/viriesu-smarzas",
        "html_out": "lab/scout_220.html",
    },
}

CANDIDATE_SELECTORS = [
    # Container candidates
    ("container", "div.c-product-card"),
    ("container", "li.c-product-card"),
    ("container", "article.c-product-card"),
    ("container", "[class*='product-card']"),
    ("container", "[class*='ProductCard']"),
    ("container", "li.product-item"),
    ("container", ".product-item"),
    ("container", "li[class*='product']"),
    ("container", "div[class*='product']"),

    # Title  
    ("title", "p.product-name a"),
    ("title", "a.c-product-card__name"),
    ("title", "h3 a"),
    ("title", "h2 a"),
    ("title", "[class*='product-name']"),
    ("title", "[class*='ProductName']"),
    ("title", "[class*='product-title']"),
    ("title", "a[class*='name']"),

    # Price
    ("price", "span.c-price--current"),
    ("price", "[class*='price']"),
    ("price", "[class*='Price']"),
    ("price", "span[class*='current']"),
    ("price", "meta[itemprop='price']"),

    # Next page
    ("next_page", "a[aria-label*='Next']"),
    ("next_page", "a[aria-label*='Nākamā']"),
    ("next_page", "a[rel='next']"),
    ("next_page", "a.c-pagination__next"),
    ("next_page", "a.next"),
    ("next_page", "[class*='pagination'] a[class*='next']"),
    ("next_page", "a[class*='next']"),
]


def analyze_html(html: str, site: str):
    soup = BeautifulSoup(html, "html.parser")
    print(f"\n{'='*60}")
    print(f"  STRUCTURE ANALYSIS: {site}")
    print(f"{'='*60}")

    from parsel import Selector
    sel = Selector(text=html)

    results = {}
    for sel_type, css in CANDIDATE_SELECTORS:
        try:
            found = sel.css(css)
            count = len(found)
            if count > 0:
                sample = found[0].xpath('string(.)').get(default="").strip()[:80]
                if sel_type not in results:
                    results[sel_type] = []
                results[sel_type].append((css, count, sample))
        except Exception:
            pass

    for sel_type in ["container", "title", "price", "next_page"]:
        matches = results.get(sel_type, [])
        if matches:
            print(f"\n📌 [{sel_type.upper()}] Candidates:")
            for css, count, sample in sorted(matches, key=lambda x: -x[1]):
                print(f"   {count:3d}x  {css:<45}  → '{sample[:60]}'")
        else:
            print(f"\n❌ [{sel_type.upper()}] No candidates found!")

    # Also print raw class names from first 5 product-looking divs/lis
    print(f"\n🔎 First few elements with 'product' in class:")
    for tag in soup.find_all(True, class_=lambda c: c and 'product' in ' '.join(c).lower())[:8]:
        classes = ' '.join(tag.get('class', []))
        text_sample = tag.get_text(strip=True)[:60]
        print(f"   <{tag.name} class='{classes}'> → '{text_sample}'")


async def fetch_html(url: str, site: str) -> str:
    logger.info(f"🔍 Fetching {site}: {url}")
    
    # Try stealth first
    html = await stealth_client.get_page(url)
    if html and len(html) > 10000 and "202 Accepted" not in html and "captcha" not in html.lower():
        logger.success(f"✅ Stealth client: {len(html)} bytes")
        return html
    
    logger.warning("⚠️ Stealth failed, using browser...")
    await stealth_client.init_session()
    resp = await browser_manager.get_page_content(url)
    if resp and resp.get("html"):
        html = resp["html"]
        logger.success(f"✅ Browser: {len(html)} bytes")
        return html
    
    return ""


async def main():
    site = sys.argv[1] if len(sys.argv) > 1 else "1a"
    
    if site not in TARGETS:
        print(f"Unknown site '{site}'. Use: 1a | 220")
        return

    target = TARGETS[site]
    url = target["url"]
    out_file = target["html_out"]

    # Check cache
    if os.path.exists(out_file) and "--fresh" not in sys.argv:
        logger.info(f"📄 Using cached HTML: {out_file} (use --fresh to re-fetch)")
        with open(out_file, "r", encoding="utf-8") as f:
            html = f.read()
    else:
        await stealth_client.init_session()
        html = await fetch_html(url, site)
        if html:
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(html)
            logger.success(f"💾 Saved to {out_file}")
        else:
            logger.error("Failed to fetch HTML!")
            return

    analyze_html(html, site)

    await browser_manager.stop()
    await stealth_client.close()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
