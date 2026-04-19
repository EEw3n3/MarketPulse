"""
Lab Results Inspector — MarketPulse
Shows scraped products grouped by source domain with clean formatting.
"""
import asyncio
import re
from datetime import datetime
from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, selectinload
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.domain.models import ScrapingRule, Product

LAB_DB_URL = "sqlite+aiosqlite:///lab/lab_test.db"
lab_engine = create_async_engine(LAB_DB_URL, echo=False)

# Force colors off to avoid terminal-specific artifacts like 'X' appearing in logs/output
USE_COLOR = False

def col(code: str, text: str) -> str:
    if not USE_COLOR:
        return text
    # Standard ANSI escape codes: \033[...m
    return f"\033[{code}m{text}\033[0m"

# Pad PLAIN text first, then apply color — avoids ANSI width miscalculation
def pc(code: str, text: str, width: int = 0, align: str = "<") -> str:
    # Using raw f-string with padding can sometimes include escape characters in width calculation
    # if not careful. But here we pad the PLAIN text first.
    padded = f"{text:{align}{width}}" if width > 0 else text
    return col(code, padded)

CYAN    = lambda t, w=0: pc("96", t, w)
GREEN   = lambda t, w=0: pc("92", t, w)
YELLOW  = lambda t, w=0: pc("93", t, w)
MAGENTA = lambda t, w=0: pc("95", t, w)
WHITE   = lambda t, w=0: pc("97", t, w)
DIM     = lambda t, w=0: pc("2",  t, w)
BOLD    = lambda t, w=0: pc("1",  t, w)
RED     = lambda t, w=0: pc("91", t, w)

CHANGE_MAP = {
    "initial":      ("new",    "2"),
    "no_change":    ("——",     "2"),
    "price_up":     ("↑ up",   "91"),
    "price_down":   ("↓ down", "92"),
    "back_in_stock":("✔ back", "92"),
    "out_of_stock": ("✘ out",  "91"),
}

_VOL_RE = re.compile(r',?\s*\d+[.,]?\d*\s*(ml|l|oz|мл|л)\b', re.IGNORECASE)

def strip_vol(title: str) -> str:
    return _VOL_RE.sub('', title).strip(' ,')

def fmt_price(price) -> str:
    return f"{float(price):>8.2f} €"

def trunc(s: str, n: int) -> str:
    s = s.replace('\n', ' ').strip()
    return s if len(s) <= n else s[:n - 1] + "…"


async def inspect():
    async_session = sessionmaker(lab_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        rules_result = await session.execute(select(ScrapingRule))
        rules = {r.domain: r for r in rules_result.scalars().all()}

        stmt = (
            select(Product)
            .options(selectinload(Product.history))
            .order_by(Product.id.desc())
            .limit(500)
        )
        products = (await session.execute(stmt)).scalars().all()

    if not products:
        print("  ⚠️  No products found in lab database.")
        return

    from urllib.parse import urlparse
    by_domain: dict[str, list] = {}
    for p in products:
        domain = urlparse(p.url).netloc.replace("www.", "") if p.url else "unknown"
        by_domain.setdefault(domain, []).append(p)

    total = len(products)
    W = 96  # table width

    print()
    print(BOLD(f"╔{'═' * W}╗"))
    header = f"🧪  MARKETPULSE LAB RESULTS  —  {total} products across {len(by_domain)} sites"
    print(BOLD("║") + CYAN(f"  {header:<{W-2}}") + BOLD("║"))
    print(BOLD(f"╚{'═' * W}╝"))

    for domain, prods in sorted(by_domain.items(), key=lambda x: -len(x[1])):
        rule   = rules.get(domain)
        store  = rule.site_name if rule else domain
        emoji  = (rule.emoji or "🛒") if rule else "🛒"
        health = rule.health_score if rule else None

        health_str = ""
        if health is not None:
            color = "92" if health > 0.7 else "91"
            health_str = col(color, f"health {health:.0%}")

        print()
        print(BOLD(f"  {emoji}  {store}") + DIM(f"  ({domain})") + f"  {health_str}")
        print(DIM("  " + "─" * W))
        # Column header (plain, dims)
        print(DIM(f"  {'ID':<6} {'BRAND':<20} {'PRICE':>10}  {'CHANGE':<10}  {'VOL':<8}  {'CONC':<7}  TITLE"))
        print(DIM("  " + "─" * W))

        for p in sorted(prods, key=lambda x: -x.id):
            # Safe access to history
            rec = p.history[-1] if (hasattr(p, 'history') and p.history) else None

            id_str     = str(p.id).ljust(6)
            brand_str  = trunc(p.brand or "—", 20).ljust(20)
            price_str  = fmt_price(rec.price) if rec else "       — €"
            vol_str    = trunc(p.volume or "—", 8).ljust(8)
            conc_str   = trunc(p.concentration or "—", 7).ljust(7)
            title_str  = trunc(strip_vol(p.title), 40)
            avail_str  = "" if p.is_available else col("91", " ✘")

            change_disp = "—"
            c_code = "2"
            if rec:
                label, c_code = CHANGE_MAP.get(rec.change_type, ("?", "2"))
                change_disp = label

            print(
                f"  {WHITE(id_str)}"
                f" {MAGENTA(brand_str)}"
                f" {GREEN(price_str) if rec else DIM(price_str)}"
                f"  {col(c_code, change_disp.ljust(10))}"
                f"  {CYAN(vol_str)}"
                f"  {YELLOW(conc_str)}"
                f"  {title_str}{avail_str}"
            )

        # Footer stats
        prices = [float(p.history[-1].price) for p in prods if p.history]
        if prices:
            avg, mn, mx = sum(prices)/len(prices), min(prices), max(prices)
            print(DIM("  " + "─" * W))
            print(
                DIM(f"  {len(prods)} products") +
                f"   avg {CYAN(f'{avg:.2f} €')}   "
                f"min {GREEN(f'{mn:.2f} €')}   "
                f"max {YELLOW(f'{mx:.2f} €')}"
            )

    print()
    print(DIM(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"))
    print()


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(inspect())
