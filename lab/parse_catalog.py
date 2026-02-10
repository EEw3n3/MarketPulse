from parsel import Selector
import json

with open("lab_debug.html", "r", encoding="utf-8") as f:
    html = f.read()

sel = Selector(text=html)
# Container from rule: div[data-testid="product-container"]
cards = sel.css('div[data-testid="product-container"]')
print(f"Cards found: {len(cards)}")

for card in cards[:5]:
    title = card.css('h3[data-testid="product-tile-name"]::text').get()
    link = card.css('a::attr(href)').get()
    print(f"Title: {title} | Link: {link}")
