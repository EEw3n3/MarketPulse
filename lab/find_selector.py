from bs4 import BeautifulSoup

with open('lab/detail_debug.html', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

print("=== Looking for variant containers ===")

# Find all span.name with ml
ml_spans = [s for s in soup.find_all('span', class_='name') if 'ml' in s.get_text()]
print(f"Found {len(ml_spans)} span.name elements with 'ml' text")

for span in ml_spans[:3]:
    p1 = span.parent
    p2 = p1.parent if p1 else None
    p3 = p2.parent if p2 else None
    p4 = p3.parent if p3 else None

    cls1 = ' '.join(p1.get('class', [])) if p1 else ''
    cls2 = ' '.join(p2.get('class', [])) if p2 else ''
    cls3 = ' '.join(p3.get('class', [])) if p3 else ''
    cls4 = ' '.join(p4.get('class', [])) if p4 else ''

    print(f"\n  span.name text: {span.get_text(strip=True)}")
    print(f"  p1: <{p1.name}> class='{cls1}'")
    print(f"  p2: <{p2.name}> class='{cls2}'")
    print(f"  p3: <{p3.name}> class='{cls3}'")
    print(f"  p4: <{p4.name}> class='{cls4}'")
    
    # Also show price sibling
    price_sib = p1.find('span', class_='price') if p1 else None
    if not price_sib:
        price_sib = p2.find('span', class_='price') if p2 else None
    print(f"  price sibling: {price_sib.get_text(strip=True) if price_sib else 'NOT FOUND'}")

print("\n=== Checking .product-sizes and similar containers ===")
for cls in ['product-sizes', 'sizes', 'variants', 'product-variant', 'product_sizes']:
    found = soup.find_all(class_=cls)
    if found:
        print(f"  .{cls}: {len(found)} element(s) found")
        el = found[0]
        children = el.find_all(recursive=False)
        print(f"    Direct children: {len(children)}")
        if children:
            c = children[0]
            c_cls = ' '.join(c.get('class', []))
            print(f"    First child: <{c.name}> class='{c_cls}'")

print("\n=== Counting repeating items in span.name with ml ===")
containers = {}
for span in ml_spans:
    p2 = span.parent.parent if span.parent else None
    if p2:
        key = (p2.name, ' '.join(p2.get('class', [])))
        containers[key] = containers.get(key, 0) + 1
for k, v in sorted(containers.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v} occurrences")
