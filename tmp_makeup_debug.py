from bs4 import BeautifulSoup
import json

with open("debug_no_id.html", "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f, "html.parser")

items = soup.find_all("li", class_="catalog-products-list__item")
if not items:
    items = soup.find_all("li", class_="simple-slider-list__item")

for item in items:
    title_el = item.find("div", class_="simple-slider-list__name") or item.find("a", class_="simple-slider-list__name") or item.find("div", class_="info-product-wrapper")
    title = title_el.text.strip() if title_el else "Unknown"
    
    if "Eros" in title or "Armaf" in title or "Montblanc" in title or True: # Just print first match
        print("======== TITLE:", title, "========")
        # Check for JSON script
        scripts = item.find_all("script", type="application/json")
        for s in scripts:
            print("FOUND JSON SCRIPT:", s.string)
        
        # Check for dropdown or list of variants
        variant_div = item.find("div", class_="variants") or item.find("ul", class_="variants-list")
        if variant_div:
            print("FOUND VARIANT DIV:", variant_div.prettify()[:500])
        else:
            # Let's just print all text content to see if volumes are hidden somewhere
            print("TEXT CONTENT:", item.get_text(separator=' | ', strip=True)[:500])
        
        # print full HTML of card to analyze if needed
        # print("HTML:")
        # print(item.prettify()[:1000])
        break
