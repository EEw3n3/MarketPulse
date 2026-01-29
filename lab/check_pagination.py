from parsel import Selector
import os

def check_html():
    if not os.path.exists("lab_debug.html"):
        print("❌ lab_debug.html not found")
        return

    with open("lab_debug.html", "r", encoding="utf-8") as f:
        html = f.read()
    
    sel = Selector(text=html)
    
    # Let's look for the pagination block
    print("--- PAGINATION SEARCH ---")
    
    # 1. Search by typical classes
    pag_selectors = [".pages", ".pagination", ".catalog-pagination", ".page-list"]
    for s in pag_selectors:
        block = sel.css(s).get()
        if block:
            print(f"✅ Found block {s}:")
            print(block)
            break
            
    # 2. Search for the next page link specifically
    print("\n--- NEXT PAGE DETECTION SIMULATION ---")
    
    # Search for active page
    active_candidates = ['is-active', 'active', 'current', 'selected', 'active-page', 'page__item_active']
    for cls in active_candidates:
        active_el = sel.xpath(f"//*[contains(@class, '{cls}')]").get()
        if active_el:
            print(f"Found active element with class '{cls}': {active_el[:200]}...")
            
            # Simulate the search for the next link
            xpath_query = f"//*[contains(@class, '{cls}')]/following-sibling::*//a/@href"
            links = sel.xpath(xpath_query).getall()
            print(f"Links found via follow-sibling: {links}")
            
    # 3. Check for the 'label' structure shown in the logs earlier
    print("\n--- LABEL STRUCTURE CHECK ---")
    labels = sel.css(".page__item label").getall()
    for l in labels[:5]:
        print(f"Label: {l}")

if __name__ == "__main__":
    check_html()
