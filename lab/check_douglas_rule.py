"""
Check which Douglas items actually went through deep dive and what happened.
Focus: Why do some "no X EUR" items end up with price=0 in the DB?
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3

conn = sqlite3.connect('lab/lab_test.db')

# All Douglas products sorted by price
print("=== ALL DOUGLAS PRODUCTS IN DB ===")
cur = conn.execute("""
    SELECT title, last_price, volume, concentration, is_available, brand, url 
    FROM product 
    WHERE search_term = 'Douglas Latvia'
    ORDER BY last_price DESC
""")
rows = cur.fetchall()
zero_ct = 0
good_ct = 0
unavail_ct = 0
for r in rows:
    price = float(r[1]) if r[1] else 0
    status = "AVAIL" if r[4] else "UNAVAIL"
    vol = r[2] or "no-vol"
    brand = r[5] or "no-brand"
    title_short = r[0][:50]
    url_short = r[6][-40:] if r[6] else ""
    
    if price == 0 and not r[4]:
        unavail_ct += 1
    elif price == 0 and r[4]:
        zero_ct += 1
    else:
        good_ct += 1
    
    marker = ""
    if price == 0 and r[4]: marker = " <<< BUG: price=0 but available!"
    if price == 0 and not r[4]: marker = " (expected: unavailable)"
    
    print(f"  {brand:16s} | {title_short:50s} | {vol:10s} | {price:8.2f}EUR | {status:8s}{marker}")

print(f"\nSummary: {good_ct} good, {unavail_ct} unavailable (expected 0), {zero_ct} BUG (price=0 but available)")
print(f"Total: {len(rows)}")

conn.close()
