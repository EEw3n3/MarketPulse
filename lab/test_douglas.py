import urllib.request
import re
import json
import html

req = urllib.request.Request('https://www.douglas.lv/lv/katalogs/lacoste-original-aqua/?item=78113', headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
        content = response.read().decode('utf-8')
        
    tealium_matches = re.finditer(r'data-tealium-info-view=.*?([{].*?[}])', content, re.DOTALL)
    for match in tealium_matches:
        text = match.group(1)
        text = html.unescape(text)
        try:
            data = json.loads(text)
            print(f"Variant: {data.get('primary_product_variant_name', [''])[0]}, Price: {data.get('primary_product_price', [''])[0]}, Stock: {data.get('primary_product_availability_status', [''])[0]}")
        except Exception as e:
            pass
except Exception as e:
    print("Error:", e)
