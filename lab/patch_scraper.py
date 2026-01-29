import sys
import os

SCRAPER_PATH = r"c:\Users\user\Market_pulse\app\services\scraper.py"

NEW_FUNC = """    def _find_next_page_fallback(self, sel: Selector, current_url: str) -> str | None:
        def clean_href(href: str | None) -> str | None:
            if not href: return None
            if href.startswith('javascript:') or href == '#': return None
            from urllib.parse import urljoin, urlparse
            if bool(urlparse(href).netloc): return href
            parsed_base = urlparse(current_url)
            base_root = f"{parsed_base.scheme}://{parsed_base.netloc}"
            return urljoin(base_root, href) if href.startswith('/') else urljoin(current_url, href)

        def is_valid_pagination(href: str) -> bool:
            if not href: return False
            junk = ['/news/', '/product/', '/ads/', '/cart/', '/login/', '/auth/']
            if any(j in href.lower() for j in junk): return False
            return True

        # 1. NUMERIC INCREMENT (Best for Makeup.lv)
        active_nodes = sel.xpath("//li[contains(@class, 'page') and (not(descendant::a) or contains(@class, 'active') or contains(@class, 'current'))]//text()[normalize-space()]").getall()
        if not active_nodes:
            active_nodes = sel.xpath("//input[@checked]/following-sibling::label//text()").getall()

        current_page_num = None
        for txt in active_nodes:
            if txt.strip().isdigit():
                current_page_num = int(txt.strip())
                break

        if current_page_num:
            next_num = current_page_num + 1
            next_num_link = sel.xpath(f"//li[contains(@class, 'page')]//a[text()='{next_num}']/@href").get()
            if not next_num_link:
                 next_num_link = sel.xpath(f"//a[text()='{next_num}']/@href").get()

            candidate = clean_href(next_num_link)
            if candidate and is_valid_pagination(candidate):
                logger.info(f"🔢 Found next page by incrementing: {current_page_num} -> {next_num} ({candidate})")
                return candidate

        # 2. SIBLING LOGIC
        active_li = sel.xpath("//li[contains(@class, 'page') and (not(descendant::a) or contains(@class, 'active'))]")
        if not active_li:
            active_li = sel.xpath("//input[@checked or @checked='checked']/ancestor::li")
        if active_li:
            next_link = active_li.xpath("./following-sibling::li[descendant::a][1]//a/@href").get()
            candidate = clean_href(next_link)
            if candidate and is_valid_pagination(candidate):
                logger.info(f"⏭️ Found next page via sibling logic: {candidate}")
                return candidate

        return None
"""

def main():
    with open(SCRAPER_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    start = -1
    end = -1
    for i, line in enumerate(lines):
        if "def _find_next_page_fallback" in line:
            start = i
        if start != -1 and "def _try_selectors" in line:
            end = i
            break

    if start != -1 and end != -1:
        new_lines = lines[:start] + [NEW_FUNC + "\n"] + lines[end:]
        with open(SCRAPER_PATH, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print("✅ SCRAPER PATCHED SUCCESSFULLY")
    else:
        print(f"❌ FAILED TO FIND BOUNDARIES: {start} to {end}")

if __name__ == "__main__":
    main()
