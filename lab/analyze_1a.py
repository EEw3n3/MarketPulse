from parsel import Selector

with open('lab/scout_1a.html', 'r', encoding='utf-8') as f:
    html = f.read()

sel = Selector(text=html)

print('=== IMG inside div.catalog-taxons-product (first 3) ===')
for card in sel.css('div.catalog-taxons-product')[:3]:
    for img in card.css('img'):
        src = img.attrib.get('src', '') or img.attrib.get('data-src', '')
        cls = img.attrib.get('class', '')
        print(f'  class={cls!r}  src={src[:100]!r}')

print()
print('=== Price inside div.catalog-taxons-product (first 3) ===')
for card in sel.css('div.catalog-taxons-product')[:3]:
    # get all price-number spans
    for span in card.css('span[class*=price-number]'):
        cls = span.attrib.get('class', '')
        text = span.xpath('string(.)').get()[:30].strip()
        print(f'  class={cls!r}  text={text!r}')
    print('  ---')

print()
print('=== Brand inside div.catalog-taxons-product (first 3) ===')
for card in sel.css('div.catalog-taxons-product')[:3]:
    # Look for brand link or span
    for el in card.css('a[class*=brand], span[class*=brand], div[class*=brand], [class*=vendor], [class*=manufacturer]'):
        cls = el.attrib.get('class', '')
        text = el.xpath('string(.)').get()[:40].strip()
        print(f'  class={cls!r}  text={text!r}')
    print('  (first card done) ---')
    break

print()
# Also count title relative to container (sanity check)
total = 0
for card in sel.css('div.catalog-taxons-product'):
    t = card.css('a.catalog-taxons-product__name')
    if t:
        total += 1
print(f'=== Cards with title: {total} / {len(sel.css("div.catalog-taxons-product"))} ===')
