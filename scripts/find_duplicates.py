"""Find possible duplicates: two cards that may be one perfume (see
app/services/group_merge.py). Nothing is merged here: an admin decides in the
admin panel → Possible duplicates.

Usage (inside the app container):
    python scripts/find_duplicates.py            # dry run: HTML report only
    python scripts/find_duplicates.py --apply    # also store them as pending pairs
"""
from __future__ import annotations

import argparse
import asyncio
import html
import os
import sys
import time
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import async_session_maker  # noqa: E402
from app.services import group_merge  # noqa: E402

REPORTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "reports"))
REASONS = {
    "conc": "Одно название, у одного магазина не указана концентрация",
    "subset": "Одно название содержит другое и ещё несколько слов",
    "typo": "Одно слово написано по-разному",
}


def e(x) -> str:
    return html.escape(str(x if x is not None else ""))


def side(g: group_merge.GroupInfo) -> str:
    vols = ", ".join(f"{v} €{p:.2f}" for v, p in sorted(g.vols.items(), key=lambda kv: group_merge.volume_sort_key(kv[0])))
    shops = ", ".join(s.replace(".lv", "") for s in sorted(g.shops))
    return f"<b>{e(g.name)}</b><br><span class=muted>{e(shops)} · {g.products} тов. · {e(vols)}</span>"


def render(pairs: list, applied: dict | None) -> str:
    rows = []
    for reason, title in REASONS.items():
        group = sorted((p for p in pairs if p[2] == reason), key=lambda p: -p[3])
        body = "".join(f"<tr><td>{side(a)}</td><td>{side(b)}</td><td class=num>{s:.0f}</td></tr>" for a, b, _, s in group)
        rows.append(f"<h2>{e(title)} ({len(group)})</h2><table><tr><th>Остаётся</th><th>Присоединяется</th>"
                    f"<th>Оценка</th></tr>{body}</table>")
    state = (f"сохранено как «ожидают решения»: новых {applied['added']}, снято {applied['dropped']}"
             if applied else "пробный прогон, база не менялась")
    return f"""<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Возможные дубли</title>
<style>body{{font:14px/1.45 system-ui,sans-serif;margin:24px;max-width:1200px;color:#1d1d1f}}
table{{border-collapse:collapse;width:100%}} td,th{{border-bottom:1px solid #eee;padding:6px 8px;text-align:left;vertical-align:top}}
.muted{{color:#777}} .num{{text-align:right}}</style></head><body>
<h1>Возможные дубли ({len(pairs)})</h1><p class="muted">{e(datetime.now().strftime("%Y-%m-%d %H:%M"))} · {e(state)}</p>
<p>Ничего не объединяется само: решение принимает админ в разделе «Дубли» админ-панели.</p>
{"".join(rows)}</body></html>"""


async def main() -> None:
    ap = argparse.ArgumentParser(description="Find possible duplicate cards.")
    ap.add_argument("--apply", action="store_true", help="store them as pending pairs (default: report only)")
    args = ap.parse_args()
    started = time.time()
    async with async_session_maker() as s:
        groups = await group_merge.load_groups(s)
        pairs = group_merge.candidate_pairs(groups)
        applied = None
        if args.apply:
            applied = await group_merge.find_pairs(s)
            await s.commit()
    print(f"{len(groups)} groups, {len(pairs)} possible duplicates ({time.time() - started:.0f} s)")
    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = os.path.join(REPORTS_DIR, f"duplicates_{datetime.now():%Y-%m-%d_%H%M}{'_applied' if args.apply else ''}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(render(pairs, applied))
    print(f"report: {path}")


if __name__ == "__main__":
    asyncio.run(main())
