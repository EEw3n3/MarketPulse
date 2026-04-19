"""
Cross-site Chain Inspector — MarketPulse
Shows ProductGroups that span multiple sites (real chains) vs single-site groups.
Reveals matcher quality: same product across Notino/Douglas/Makeup/220/1a should chain.
"""
import asyncio
import sys
import os
from decimal import Decimal
from urllib.parse import urlparse
from collections import defaultdict

from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, selectinload

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.domain.models import ProductGroup, Product

LAB_DB_URL = "sqlite+aiosqlite:///lab/lab_test.db"
lab_engine = create_async_engine(LAB_DB_URL, echo=False)


def domain_of(url: str) -> str:
    if not url:
        return "unknown"
    return urlparse(url).netloc.replace("www.", "").replace(".lv", "")


def fmt_price(p) -> str:
    if p is None:
        return "   — €"
    return f"{float(p):>6.2f} €"


def trunc(s: str, n: int) -> str:
    s = (s or "").replace("\n", " ").strip()
    return s if len(s) <= n else s[:n - 1] + "…"


async def inspect_chains():
    async_session = sessionmaker(lab_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        stmt = (
            select(ProductGroup)
            .options(selectinload(ProductGroup.products))
            .order_by(ProductGroup.id)
        )
        groups = (await session.execute(stmt)).scalars().all()

        total_products = (await session.execute(select(Product))).scalars().all()

    if not groups:
        print("⚠️  No ProductGroups found. Run lab_runner first.")
        return

    # Bucket groups by distinct-site count
    multi_site: list[tuple[ProductGroup, set[str]]] = []
    single_site: list[tuple[ProductGroup, set[str]]] = []
    empty: list[ProductGroup] = []

    for g in groups:
        if not g.products:
            empty.append(g)
            continue
        sites = {domain_of(p.url) for p in g.products if p.url}
        if len(sites) >= 2:
            multi_site.append((g, sites))
        else:
            single_site.append((g, sites))

    multi_site.sort(key=lambda x: (-len(x[1]), -len(x[0].products)))

    total_groups = len(groups)
    cross_count = len(multi_site)
    single_count = len(single_site)

    print()
    print("╔" + "═" * 100 + "╗")
    print(f"║  🔗  CROSS-SITE CHAIN ANALYSIS — {len(total_products)} products in {total_groups} groups".ljust(101) + "║")
    print("╠" + "═" * 100 + "╣")
    print(f"║  ✅  Cross-site chains (≥2 sites): {cross_count:>4}   ({cross_count/total_groups*100:.1f}%)".ljust(101) + "║")
    print(f"║  ◻️   Single-site groups:           {single_count:>4}   ({single_count/total_groups*100:.1f}%)".ljust(101) + "║")
    print(f"║  ⚠️   Empty groups:                 {len(empty):>4}".ljust(101) + "║")
    print("╚" + "═" * 100 + "╝")

    # Site coverage breakdown for cross-site chains
    coverage = defaultdict(int)  # N sites → count
    for g, sites in multi_site:
        coverage[len(sites)] += 1
    if coverage:
        print("\n  📊 Cross-site coverage breakdown:")
        for n in sorted(coverage.keys(), reverse=True):
            bar = "█" * coverage[n]
            print(f"     {n} sites: {coverage[n]:>3}  {bar}")

    # Pairwise site overlap matrix (how often do sites chain together)
    pair_counts = defaultdict(int)
    for g, sites in multi_site:
        sites_sorted = sorted(sites)
        for i, s1 in enumerate(sites_sorted):
            for s2 in sites_sorted[i + 1:]:
                pair_counts[(s1, s2)] += 1

    if pair_counts:
        print("\n  🔀 Pair overlap (how often 2 sites chain):")
        for (s1, s2), count in sorted(pair_counts.items(), key=lambda x: -x[1]):
            print(f"     {s1:<10} ↔ {s2:<10}  {count} chains")

    # === Detailed cross-site chains ===
    print()
    print("═" * 102)
    print(f"  🔗 CROSS-SITE CHAINS (top {min(50, len(multi_site))} by site count, then variant count)")
    print("═" * 102)

    for g, sites in multi_site[:50]:
        products = sorted(g.products, key=lambda p: (domain_of(p.url), float(p.last_price or 0)))

        print()
        print(f"  🧬 [{g.id}] {g.name}   ({len(sites)} sites · {len(g.products)} variants)")
        print("  " + "─" * 100)
        print(f"  {'SITE':<10} {'BRAND':<18} {'VOL':<8} {'PRICE':>10}  TITLE")
        print("  " + "─" * 100)

        for p in products:
            site = domain_of(p.url)
            brand = trunc(p.brand or "—", 18)
            vol = trunc(p.volume or "—", 8)
            price = fmt_price(p.last_price)
            title = trunc(p.title, 48)
            avail = "" if p.is_available else "  ✘ OOS"
            print(f"  {site:<10} {brand:<18} {vol:<8} {price:>10}  {title}{avail}")

        # Best price per volume
        by_vol = defaultdict(list)
        for p in g.products:
            if p.last_price and p.last_price > 0:
                by_vol[(p.volume or "?")].append((domain_of(p.url), float(p.last_price)))
        if by_vol:
            print("  " + "─" * 100)
            for vol, offers in sorted(by_vol.items()):
                if len(offers) >= 2:
                    offers.sort(key=lambda x: x[1])
                    best_site, best_price = offers[0]
                    worst_site, worst_price = offers[-1]
                    diff_pct = (worst_price - best_price) / best_price * 100
                    print(f"     💰 {vol:<8}  best: {best_site} {best_price:.2f}€   "
                          f"vs {worst_site} {worst_price:.2f}€   (+{diff_pct:.0f}%)")

    # === Sample of single-site groups (potential chaining failures) ===
    print()
    print("═" * 102)
    print(f"  ◻️  SAMPLE OF SINGLE-SITE GROUPS (these MIGHT have unmatched siblings on other sites)")
    print("═" * 102)

    # Group by site for overview
    by_site_single = defaultdict(int)
    for g, sites in single_site:
        for s in sites:
            by_site_single[s] += 1
    print("\n  Single-site groups by site:")
    for site, n in sorted(by_site_single.items(), key=lambda x: -x[1]):
        print(f"     {site:<12} {n:>4} groups")

    # Show 20 examples from each site that have NO cross-site match
    print("\n  📋 20 random single-site groups (check manually if they exist on other sites):")
    shown = 0
    for g, sites in single_site:
        if shown >= 20:
            break
        site = list(sites)[0]
        n_variants = len(g.products)
        brand = g.products[0].brand if g.products else "—"
        print(f"     [{site:<10}] {brand:<18}  {trunc(g.name, 60)}  ({n_variants} var.)")
        shown += 1

    print()
    print("  💡 Quality indicators:")
    print("     - High cross-site % = matcher is working")
    print("     - Low cross-site % with known duplicates = matcher is too strict or normalizer diverges")
    print("     - Check single-site groups: if a Notino product exists on Douglas but didn't chain → bug")
    print()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(inspect_chains())
