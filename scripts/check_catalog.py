"""Read-only checks of the catalogue endpoints against the local database.

Run inside the app container:

    docker compose -p marketpulse exec -T app python scripts/check_catalog.py

It calls the real endpoints through the ASGI app (no network, no writes; the
login is replaced by a stub) and compares every answer with an independent
count taken straight from the products table.

Checked:
  1. a card filtered to one shop still says how many shops sell the bottle;
     "Sold in 2+ shops" works together with a shop filter;
  4. /products/filters?brands=… counts sizes for that brand only;
  5. in_stock=false returns only listings the shop has run out of.
"""
from __future__ import annotations

import asyncio
import os
import sys
from collections import defaultdict
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.api import cards as cards_api  # noqa: E402
from app.api.deps import get_current_user  # noqa: E402
from app.api.exports import _filters_desc  # noqa: E402
from app.api.main import app  # noqa: E402
from app.core.database import async_session_maker  # noqa: E402
from app.domain.models import Product  # noqa: E402
from app.services.price_series import store_key  # noqa: E402

SHOPS = ["douglas", "notino", "makeup", "220"]
FAILED: list[str] = []
PASSED = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASSED
    if ok:
        PASSED += 1
        print(f"  ok    {name}{' — ' + detail if detail else ''}")
    else:
        FAILED.append(name)
        print(f"  FAIL  {name}{' — ' + detail if detail else ''}")


async def load_products() -> list[Product]:
    async with async_session_maker() as db:
        return list((await db.execute(select(Product).where(Product.last_price > 0))).scalars().all())


def truth(products: list[Product]):
    """Per card key: every shop that lists it, and the shops that have it in stock."""
    all_shops: dict[str, set[str]] = defaultdict(set)
    live_shops: dict[str, set[str]] = defaultdict(set)
    for p in products:
        k = cards_api.card_key(p)
        all_shops[k].add(store_key(p.search_term))
        if p.is_available:
            live_shops[k].add(store_key(p.search_term))
    return all_shops, live_shops


async def all_cards(client: httpx.AsyncClient, **params) -> tuple[int, list[dict]]:
    """Every card for the filters (paged), with the total the endpoint reports."""
    items: list[dict] = []
    total = 0
    skip = 0
    while True:
        r = await client.get("/api/products/cards", params={**params, "skip": skip, "limit": 96})
        r.raise_for_status()
        page = r.json()
        total = page["total"]
        items += page["items"]
        skip += 96
        if not page["items"] or skip >= total or skip >= 960:
            return total, items


async def main() -> int:
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=0, is_admin=True, is_active=True)
    cards_api._FACETS_CACHE.update(at=0.0, value=None)
    products = await load_products()
    all_shops, live_shops = truth(products)
    expect_total = {k: len(live_shops[k]) or len(all_shops[k]) for k in all_shops}
    print(f"{len(products)} priced listings, {len(all_shops)} cards in the local database\n")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=120) as client:
        print("1. Shop count on a card")
        _, plain = await all_cards(client)
        check("no filter: shops_total matches the database",
              all(c["shops_total"] == expect_total[c["key"]] for c in plain), f"{len(plain)} cards")
        for shop in SHOPS:
            total, items = await all_cards(client, stores=shop)
            if not items:
                check(f"{shop}: has cards", False, "no cards at all")
                continue
            only_shop = all({o["store"] for o in c["offers"]} == {shop} for c in items)
            right = [c for c in items if c["shops_total"] == expect_total[c["key"]]]
            many = sum(1 for c in items if c["shops_total"] >= 2)
            check(f"{shop}: cards show only this shop's offers", only_shop, f"{len(items)} of {total} cards read")
            check(f"{shop}: shops_total matches the database on every card", len(right) == len(items),
                  f"{many} cards are sold in 2+ shops")
            check(f"{shop}: some cards are in 2+ shops (was always 1 before)", many > 0)

            m_total, m_items = await all_cards(client, stores=shop, multi_shop="true")
            want = sum(1 for k, s in all_shops.items() if shop in s and len(s) >= 2)
            check(f"{shop} + Sold in 2+ shops: total matches the database", m_total == want, f"{m_total} cards (was 0 before)")
            check(f"{shop} + Sold in 2+ shops: every card is listed by 2+ shops",
                  all(len(all_shops[c["key"]]) >= 2 for c in m_items))
        m_total, _ = await all_cards(client, multi_shop="true")
        check("Sold in 2+ shops without a shop filter: total unchanged",
              m_total == sum(1 for s in all_shops.values() if len(s) >= 2), f"{m_total} cards")
        r = await client.get("/api/products/cards", params={"sort": "shops", "limit": 24})
        counts = [len(all_shops[c["key"]]) for c in r.json()["items"]]
        check("sort by shops: descending", counts == sorted(counts, reverse=True), str(counts[:6]))

        print("\n4. Sizes for the picked brand")
        general = (await client.get("/api/products/filters")).json()
        gen_vols = {v["value"]: v["count"] for v in general["volumes"]}
        want_gen: dict[str, int] = defaultdict(int)
        for p in products:
            if p.volume:
                want_gen[p.volume] += 1
        check("no brand: sizes are catalogue-wide", gen_vols == dict(want_gen), f"{len(gen_vols)} sizes")
        top_brands = [b["value"] for b in general["brands"][:6]]
        for brand in top_brands + ["dior", "YSL"]:
            got = (await client.get("/api/products/filters", params={"brands": brand})).json()
            vols = {v["value"]: v["count"] for v in got["volumes"]}
            # The same listings the catalogue shows for this brand, counted through the listings endpoint.
            want: dict[str, int] = defaultdict(int)
            skip = 0
            while True:
                page = (await client.get("/api/products/listings", params={"brands": brand, "sort": "price", "skip": skip, "limit": 200})).json()
                for row in page["items"]:
                    if row["volume"]:
                        want[row["volume"]] += 1
                skip += 200
                if skip >= page["total"]:
                    break
            check(f"{brand}: sizes and counts equal the brand's listings", vols == dict(want),
                  f"{len(vols)} sizes, {sum(vols.values())} listings")
            check(f"{brand}: differs from the general list", vols != gen_vols)
            check(f"{brand}: the other facets stay catalogue-wide",
                  got["brands"] == general["brands"] and got["stores"] == general["stores"])
        two = (await client.get("/api/products/filters", params=[("brands", top_brands[0]), ("brands", top_brands[1])])).json()
        one_a = (await client.get("/api/products/filters", params={"brands": top_brands[0]})).json()
        one_b = (await client.get("/api/products/filters", params={"brands": top_brands[1]})).json()
        s2, sa, sb = (sum(v["count"] for v in x["volumes"]) for x in (two, one_a, one_b))
        check("two brands: counts add up", max(sa, sb) <= s2 <= sa + sb, f"{sa} + {sb} -> {s2}")
        none = (await client.get("/api/products/filters", params={"brands": "no-such-brand-xyz"})).json()
        check("unknown brand: no sizes, no error", none["volumes"] == [])
        again = (await client.get("/api/products/filters")).json()
        check("after brand requests the general list is intact", again["volumes"] == general["volumes"])

        print("\n5. Out-of-stock filter")
        tot_all = (await client.get("/api/products/listings", params={"limit": 1})).json()["total"]
        tot_in = (await client.get("/api/products/listings", params={"limit": 1, "in_stock": "true"})).json()["total"]
        out_page = (await client.get("/api/products/listings", params={"limit": 200, "in_stock": "false"})).json()
        want_out = sum(1 for p in products if not p.is_available)
        check("table: out-of-stock total matches the database", out_page["total"] == want_out, f"{want_out} listings")
        check("table: in stock + out of stock = all", tot_in + out_page["total"] == tot_all, f"{tot_in} + {out_page['total']} = {tot_all}")
        check("table: every row is out of stock", bool(out_page["items"]) and all(not r["in_stock"] for r in out_page["items"]))
        c_total, c_items = await all_cards(client, in_stock="false")
        check("cards: every offer shown is out of stock",
              bool(c_items) and all(not o["in_stock"] for c in c_items for o in c["offers"]), f"{c_total} cards")
        want_cards = len({cards_api.card_key(p) for p in products if not p.is_available})
        check("cards: total matches the database", c_total == want_cards, f"{want_cards} cards")
        for shop in SHOPS:
            t, items = await all_cards(client, in_stock="false", stores=shop)
            want_s = len({cards_api.card_key(p) for p in products if not p.is_available and store_key(p.search_term) == shop})
            ok = all(not o["in_stock"] and o["store"] == shop for c in items for o in c["offers"])
            check(f"cards: out of stock at {shop}", t == want_s and ok, f"{t} cards")
        _, in_items = await all_cards(client, in_stock="true")
        check("cards: In stock still shows only in-stock offers", all(o["in_stock"] for c in in_items for o in c["offers"]))
        check("export description names the filter", "out of stock" in _filters_desc(in_stock=False))
        check("export description: in stock unchanged", "in stock" in _filters_desc(in_stock=True) and "out of" not in _filters_desc(in_stock=True))
        r = await client.get("/api/exports/catalog", params={"format": "csv", "view": "listings", "in_stock": "false", "limit": 50})
        check("export with in_stock=false answers 200", r.status_code == 200, f"{len(r.content)} bytes")

    app.dependency_overrides.clear()
    print(f"\n{PASSED} checks passed, {len(FAILED)} failed")
    for f in FAILED:
        print("  failed:", f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
