from parsel import Selector

with open('lab/scout_220_rendered.html', 'r', encoding='utf-8') as f:
    html = f.read()

sel = Selector(text=html)
cards = sel.css('div.c-product-card')

print('=== Raw HTML of price element (first 3 cards) ===')
for i, card in enumerate(cards[:3]):
    price_el = card.css('.c-price:not(.h-price--loyalty)')
    if price_el:
        raw = price_el[0].get()[:300]
        print(f'Card {i+1}: {raw}')
    print()

print('=== data-* attributes on price elements ===')
for i, card in enumerate(cards[:3]):
    for el in card.css('[data-price], [data-value], [data-amount]'):
        print(f'  Card {i+1}: {el.get()[:200]}')

print()
print('=== JSON-LD / structured data ===')
for script in sel.css('script[type="application/ld+json"]::text').getall():
    print(f'  {script[:300]}')

print()
print('=== data-* on c-product-card itself (first 3) ===')
for i, card in enumerate(cards[:3]):
    attrs = {k: v for k, v in card.attrib.items()}
    print(f'  Card {i+1}: {attrs}')

print()
print('=== paginator links ===')
for el in sel.css('[class*=pagination] a, [class*=paginator] a, nav a[href*=page]')[:10]:
    href = el.attrib.get('href', '')
    cls = el.attrib.get('class', '')
    text = el.xpath('string(.)').get()[:20].strip()
    if href:
        print(f'  class={cls!r}  href={href!r}  text={text!r}')
