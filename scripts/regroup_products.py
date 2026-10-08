"""Regroup every perfume into comparison groups with the current normalizer.

Why this exists
---------------
The matcher runs only for products WITHOUT a group, so a fix in
normalizer.py / matcher.py does not touch the groups made before it. This
script rebuilds all groups from the stored product rows, the same way the live
matcher would build them today:

  * products are taken newest first (last_seen), each one joins the first
    group of its brand + concentration whose name matches (names_match), else
    it starts a group named by get_canonical_name;
  * a product without a name (the stored title is only the brand) gets no
    group: such titles lost their name in an older normalizer and cannot be
    compared; the next scrape of that product writes a full title and matches it;
  * gift sets keep no group;
  * every product's brand is set to its one display spelling (canonical_brand),
    so the brand filter shows "Hermès" once instead of HERMÈS / Hermes / Hermès.

Existing group ids are kept where possible (the group that held most of a new
group's products keeps its id and gets the new name); groups left without
products are deleted.

Safety
------
* DRY RUN by default: writes reports/regroup_<YYYY-MM-DD_HHMM>.html with every
  change and touches nothing.
* --apply performs the changes in ONE transaction. Back up the DB first.

Usage (inside the app container):
    python scripts/regroup_products.py            # dry run + HTML report
    python scripts/regroup_products.py --apply    # change the database
"""
from __future__ import annotations

import argparse
import asyncio
import html
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text

from app.core.database import async_session_maker
from app.services.matcher import MatcherService
from app.services.normalizer import brand_key, canonical_brand, name_key, names_match, perfume_normalizer

REPORTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "reports"))


def plan_groups(products: list[dict], old_names: dict[int, str]) -> dict:
    """Assign every product a new group. Returns the plan (no DB access)."""
    matcher = MatcherService()
    order = sorted(products, key=lambda p: (-(p["last_seen"].timestamp() if p["last_seen"] else 0), p["id"]))

    clusters: list[dict] = []                       # {name, brand, conc, key, members}
    by_bucket: dict[tuple[str, str], list[dict]] = defaultdict(list)
    by_name: dict[str, dict] = {}
    no_name: list[dict] = []
    collisions: list[tuple[dict, dict]] = []        # (product, cluster joined by name only)

    for p in order:
        if p["card_type"] != "perfume":
            p["new_cluster"] = None
            continue
        norm = perfume_normalizer.extract_all(p["title"] or "", explicit_brand=p["brand"])
        brand = norm["brand"]
        conc = (p["concentration"] or norm["concentration"] or "").lower()
        if not brand or not norm["clean_name"]:
            p["new_cluster"] = None
            no_name.append(p)
            continue
        key = name_key(norm["clean_name"], brand)
        bucket = by_bucket[(brand_key(brand), conc)]
        found = None
        for c in bucket:
            if c["key"] is not None and names_match(key, c["key"]):
                found = c
                break
        if found is None:
            name = matcher.get_canonical_name(p["title"], brand=brand, concentration=p["concentration"] or norm["concentration"])
            found = by_name.get(name.lower())
            if found is not None:
                # The live scraper would hit ON CONFLICT on the name and join it too.
                collisions.append((p, found))
            else:
                parsed = matcher.parse_group_name(name, brand)
                found = {
                    "name": name, "brand": brand, "conc": conc, "members": [],
                    "key": parsed[1] if parsed and parsed[0] == conc else None,
                }
                if found["key"] is None or not names_match(key, found["key"]):
                    found["unstable"] = True  # the live matcher would not find it again
                clusters.append(found)
                bucket.append(found)
                by_name[name.lower()] = found
        found["members"].append(p)
        p["new_cluster"] = found

    # Keep the old group id that holds most of each new group's products.
    taken: set[int] = set()
    for c in sorted(clusters, key=lambda c: -len(c["members"])):
        counts = Counter(m["group_id"] for m in c["members"] if m["group_id"])
        c["group_id"] = c["kept_id"] = next((gid for gid, _ in counts.most_common() if gid not in taken), None)
        if c["group_id"]:
            taken.add(c["group_id"])
    return {"clusters": clusters, "no_name": no_name, "collisions": collisions,
            "kept_ids": taken, "deleted_ids": set(old_names) - taken}


def e(x) -> str:
    return html.escape(str(x if x is not None else ""))


def product_line(p: dict) -> str:
    return (f'<li><span class="shop">{e(p["search_term"])}</span> {e(p["title"])} '
            f'<span class="muted">· {e(p["concentration"] or "без конц.")} · id {p["id"]}'
            f' · было: {e(p["old_group_name"] or "без группы")}</span></li>')


def render_report(plan: dict, products: list[dict], old_names: dict[int, str], brand_changes: Counter,
                  applied: bool) -> str:
    clusters = plan["clusters"]
    perfumes = [p for p in products if p["card_type"] == "perfume"]
    multi_shop_before = sum(1 for gid in {p["group_id"] for p in perfumes if p["group_id"]}
                            if len({q["search_term"] for q in perfumes if q["group_id"] == gid}) > 1)
    multi_shop_after = sum(1 for c in clusters if len({m["search_term"] for m in c["members"]}) > 1)

    # Old groups that are split: their products now sit in 2+ new groups.
    split: dict[int, list[dict]] = defaultdict(list)
    for p in perfumes:
        if p["group_id"]:
            split[p["group_id"]].append(p)
    split_rows = []
    for gid, members in sorted(split.items(), key=lambda kv: -len(kv[1])):
        new = defaultdict(list)
        for m in members:
            new[m["new_cluster"]["name"] if m["new_cluster"] else "— без группы (нет названия)"].append(m)
        if len(new) > 1:
            split_rows.append(
                f'<details><summary><b>{e(old_names.get(gid))}</b> → {len(new)} групп</summary><ul>'
                + "".join(f'<li><b>{e(n)}</b><ul>{"".join(product_line(m) for m in ms)}</ul></li>'
                          for n, ms in sorted(new.items()))
                + "</ul></details>")

    # New groups gathered from 2+ old groups.
    merged_rows = []
    for c in sorted(clusters, key=lambda c: -len(c["members"])):
        olds = Counter(m["old_group_name"] or "— без группы" for m in c["members"])
        if len(olds) > 1:
            merged_rows.append(
                f'<details><summary><b>{e(c["name"])}</b> ← {len(olds)} групп: '
                f'{e("; ".join(olds))}</summary><ul>{"".join(product_line(m) for m in c["members"])}</ul></details>')

    renamed = [(old_names[c["kept_id"]], c["name"]) for c in clusters
               if c["kept_id"] and old_names[c["kept_id"]] != c["name"]]
    unstable = [c for c in clusters if c.get("unstable")]
    no_name = plan["no_name"]

    stats = [
        ("товаров-духов", len(perfumes)),
        ("групп было", len(old_names)),
        ("групп станет", len(clusters)),
        ("групп с 2+ магазинами было / станет", f"{multi_shop_before} / {multi_shop_after}"),
        ("старых групп разделится", len(split_rows)),
        ("новых групп собрано из нескольких", len(merged_rows)),
        ("групп переименуется", len(renamed)),
        ("новых групп создастся", sum(1 for c in clusters if not c["kept_id"])),
        ("групп удалится (остались пустыми)", len(plan["deleted_ids"])),
        ("товаров без группы (в названии только бренд)", len(no_name)),
        ("товаров с исправленным написанием бренда", sum(brand_changes.values())),
    ]
    stat_html = "".join(f"<tr><td>{e(k)}</td><td><b>{e(v)}</b></td></tr>" for k, v in stats)
    brand_html = "".join(f"<li>{e(a)} → <b>{e(b)}</b>: {n}</li>" for (a, b), n in brand_changes.most_common())
    renamed_html = "".join(f"<li>{e(a)} → <b>{e(b)}</b></li>" for a, b in sorted(renamed))
    unstable_html = "".join(f'<li><b>{e(c["name"])}</b> ({len(c["members"])} тов.)</li>' for c in unstable)
    collision_html = "".join(f'<li>{e(p["title"])} ({e(p["search_term"])}) → <b>{e(c["name"])}</b></li>'
                             for p, c in plan["collisions"])
    state = "ИЗМЕНЕНИЯ ПРИМЕНЕНЫ" if applied else "пробный прогон, база не менялась"
    return f"""<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Перегруппировка товаров</title>
<style>body{{font:14px/1.45 system-ui,sans-serif;margin:24px;max-width:1200px;color:#1d1d1f}}
h2{{margin-top:28px}} details{{margin:4px 0;padding:4px 8px;border:1px solid #ddd;border-radius:6px}}
summary{{cursor:pointer}} .muted{{color:#777}} .shop{{display:inline-block;min-width:80px;color:#555}}
table td{{padding:2px 12px 2px 0}} input{{padding:6px;width:360px;margin:8px 0}}</style></head><body>
<h1>Перегруппировка товаров</h1><p class="muted">{e(datetime.now().strftime("%Y-%m-%d %H:%M"))} · {state}</p>
<table>{stat_html}</table>
<input id="q" placeholder="Поиск по названию группы или товара" oninput="
  const q=this.value.toLowerCase();document.querySelectorAll('details').forEach(d=>d.style.display=d.textContent.toLowerCase().includes(q)?'':'none')">
<h2>Старые группы, которые разделятся ({len(split_rows)})</h2>{"".join(split_rows)}
<h2>Новые группы из нескольких старых ({len(merged_rows)})</h2>{"".join(merged_rows)}
<h2>Товары без группы: в названии только бренд ({len(no_name)})</h2>
<details><summary>список</summary><ul>{"".join(product_line(p) for p in no_name)}</ul></details>
<h2>Переименования групп ({len(renamed)})</h2><details><summary>список</summary><ul>{renamed_html}</ul></details>
<h2>Написание брендов ({sum(brand_changes.values())} товаров)</h2><details><summary>список</summary><ul>{brand_html}</ul></details>
<h2>Названия групп, которые сопоставитель не узнаёт ({len(unstable)})</h2>
<p class="muted">Новый товар такой группы найдёт её только по совпадению названия целиком.</p>
<details><summary>список</summary><ul>{unstable_html}</ul></details>
<h2>Совпадения по названию группы ({len(plan["collisions"])})</h2>
<details><summary>список</summary><ul>{collision_html}</ul></details>
</body></html>"""


async def main() -> None:
    ap = argparse.ArgumentParser(description="Rebuild the perfume comparison groups.")
    ap.add_argument("--apply", action="store_true", help="change the database (default: dry run)")
    args = ap.parse_args()
    started = time.time()

    async with async_session_maker() as s:
        old_names = {gid: name for gid, name in (await s.execute(text("SELECT id, name FROM productgroup"))).all()}
        rows = (await s.execute(text(
            "SELECT id, title, brand, concentration, card_type, group_id, last_seen, search_term FROM product"
        ))).mappings().all()
    products = [dict(r) for r in rows]
    for p in products:
        p["old_group_name"] = old_names.get(p["group_id"])
    print(f"{len(products)} products, {len(old_names)} groups loaded")

    plan = plan_groups(products, old_names)
    brand_changes: Counter = Counter()
    for p in products:
        canon = canonical_brand(p["brand"]) if p["brand"] else p["brand"]
        p["new_brand"] = canon
        if canon != p["brand"]:
            brand_changes[(p["brand"], canon)] += 1
    print(f"planned {len(plan['clusters'])} groups in {time.time() - started:.0f} s")

    if args.apply:
        async with async_session_maker() as s:
            async with s.begin():
                clusters = plan["clusters"]
                # Free every kept group's name first: new names may swap between groups.
                for c in clusters:
                    if c["group_id"]:
                        await s.execute(text("UPDATE productgroup SET name = :n WHERE id = :i"),
                                        {"n": f"__regroup_{c['group_id']}", "i": c["group_id"]})
                await s.execute(text("UPDATE product SET group_id = NULL"))
                if plan["deleted_ids"]:
                    await s.execute(text("DELETE FROM productgroup WHERE id = ANY(:ids)"),
                                    {"ids": list(plan["deleted_ids"])})
                for c in clusters:
                    if c["group_id"]:
                        await s.execute(text("UPDATE productgroup SET name = :n WHERE id = :i"),
                                        {"n": c["name"], "i": c["group_id"]})
                    else:
                        c["group_id"] = (await s.execute(text(
                            "INSERT INTO productgroup (name, category, created_at) "
                            "VALUES (:n, 'Perfume', now() AT TIME ZONE 'utc') RETURNING id"
                        ), {"n": c["name"]})).scalar_one()
                    await s.execute(text("UPDATE product SET group_id = :g WHERE id = ANY(:ids)"),
                                    {"g": c["group_id"], "ids": [m["id"] for m in c["members"]]})
                for (old, new), _ in brand_changes.items():
                    await s.execute(text("UPDATE product SET brand = :new WHERE brand = :old"),
                                    {"new": new, "old": old})
        print("applied")

    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = os.path.join(REPORTS_DIR, f"regroup_{datetime.now():%Y-%m-%d_%H%M}{'_applied' if args.apply else ''}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_report(plan, products, old_names, brand_changes, args.apply))
    print(f"report: {path} ({time.time() - started:.0f} s)")


if __name__ == "__main__":
    asyncio.run(main())
