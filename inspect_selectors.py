from parsel import Selector
import json

with open("lab_debug.html", "r", encoding="utf-8") as f:
    html = f.read()

sel = Selector(text=html)

# Try to find a product card by text "TOM FORD Noir Extreme"
# It's in the JSON-LD, but we want the DOM element.
# Usually link contains the title or image has alt.

print("--- Searching for product container ---")
# Finding the anchor tag for the specific product
links = sel.xpath("//a[contains(@href, 'noir-extreme-smarzudensedp-vriesiem')]")
print(f"Found {len(links)} links for 'TOM FORD Noir Extreme'.")

for i, link in enumerate(links):
    print(f"\nLink Price Structure:")
    # Look for price container
    price_container = link.xpath(".//div[contains(text(), '€') or contains(., '€')]")
    if price_container:
        print(f"  Price container: {price_container[0].xpath('name()').get()} class='{price_container[0].xpath('@class').get()}'")
        print(f"  Inner HTML: {price_container[0].screen()}")
    else:
        print("  Price container not found via xpath text search.")

    # Check for test-ids
    print(f"  Data-testids found: {link.xpath('.//*[@data-testid]/@data-testid').getall()}")

print("\n--- Pagination ---")
next_btn = sel.css('a[rel="next"], a[aria-label="Next"], a:contains("Nākamā")')
print(f"Next button: {next_btn}")
if next_btn:
    print(f"  href: {next_btn.attrib.get('href')}")
    print(f"  class: {next_btn.attrib.get('class')}")

print("\n--- JSON-LD check ---")
scripts = sel.css('script[type="application/ld+json"]::text').getall()
print(f"Found {len(scripts)} JSON-LD blocks.")
