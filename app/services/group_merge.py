"""Possible duplicates: two cards that may be one perfume.

The matcher puts a new product into a group only when every word of the name
has its twin in the group name (normalizer.names_match), with the same
concentration. That keeps "Molecule 01" and "Molecule 02" apart, but leaves
the same perfume in two groups when one shop writes the name differently:

  * one name has extra words: "Armaf Desert Breeze" / "Armaf Eter Desert Breeze",
    "Moonlight Patchouli" / "Collection Extraordinaire Moonlight Patchouli";
  * one word is spelled differently: "Philipp Plein No Limit$" / "No Limits";
  * one shop gives no concentration: "Montale Bengal Oud" / "... Bengal Oud EDP".

find_pairs() looks for such pairs among groups of the same brand that are sold
in different shops, share a volume and cost about the same, and stores them as
"pending" GroupPair rows. Nothing is merged automatically: an admin looks at the
two cards side by side and merges them (undoable) or keeps them apart. A wrong
merge is worse than a duplicate: the user would see another perfume's price as
"cheaper".
"""
from __future__ import annotations

import asyncio
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from loguru import logger
from rapidfuzz import fuzz
from sqlalchemy import or_, select, text, update

from app.domain.models import GroupPair, Product, ProductGroup
from app.services.normalizer import (
    _same_word, brand_key, canonical_brand, name_key, names_match, perfume_normalizer,
)

# Prices of the same volume further apart than this are another product
# (a tester, a set, another concentration) or a wrong price.
MAX_PRICE_RATIO = 2.5
# Words that make another perfume of the line when only one name has them
# ("1 Million" / "1 Million Royal", "L.12.12 Blanc" / "... Eau Intense").
FLANKER_WORDS = frozenset("""
    intense intensely intensive intensa intenso elixir extreme absolu absolute extrait concentre concentree
    forte royal platinum prive privee essence edition limited collector exclusive reserve
    noir noire black nero blue bleu blu gold oro silver argent red rouge rosso white blanc bianco brown
    green verde pink rosa purple orange grey gray night nuit notte day sport fresh fraiche fraicheur
    aqua acqua cologne eau leau summer winter spring love leather cuir oud musk vanilla vanille tobacco
    tabac wood woods rose amber ambre cherry coffee iris vetiver lavender neroli citrus marine
    original classic new pure ultra super extra mini travel set refill tester oil aromatizeta
    lidzeklis izsmidzinataja izsmidzinataju body hair deo shower
    oceanic reborn infinite teal flora azure wild incense ice tonic overdose exclusif le
    divine divina power sparkling absolutely bold victory melns melna zils zila balts balta
    sarkans sarkana zelta sudraba
""".split())


@dataclass
class GroupInfo:
    id: int
    name: str
    brand: str
    bkey: str
    conc: str
    key: dict
    shops: set = field(default_factory=set)
    vols: dict = field(default_factory=dict)     # volume → lowest price
    products: int = 0


def _digits(words) -> set:
    return {w for w in words if any(c.isdigit() for c in w)}


def classify(a: GroupInfo, b: GroupInfo) -> Optional[tuple[str, float]]:
    """(reason, score) when a and b may be one perfume, else None.
    reason: "conc" (same name, one side without concentration), "subset" (one
    name is the other plus a few words), "typo" (one word spelled differently)."""
    common = set(a.vols) & set(b.vols)
    if not common:
        return None
    if a.key["gender"] and b.key["gender"] and a.key["gender"] != b.key["gender"]:
        return None
    if a.conc and b.conc and a.conc != b.conc:
        return None
    wa, wb = a.key["words"], b.key["words"]
    if not wa or not wb or _digits(wa) != _digits(wb):
        return None
    ratio = max(max(a.vols[v], b.vols[v]) / max(min(a.vols[v], b.vols[v]), 0.01) for v in common)
    if ratio > MAX_PRICE_RATIO:
        return None
    price_bonus = 5 if ratio <= 1.3 else 0
    if names_match(a.key, b.key):
        if a.conc == b.conc:
            return None  # the matcher joins these itself (a regroup does it for old rows)
        return "conc", 90 + price_bonus
    ua = {w for w in wa if not any(_same_word(w, v) for v in wb)}
    ub = {w for w in wb if not any(_same_word(w, v) for v in wa)}
    extra = ua | ub
    if extra & FLANKER_WORDS:
        return None
    if not ua or not ub:
        return "subset", max(50, 85 - 5 * len(extra)) + price_bonus
    if len(ua) == 1 and len(ub) == 1:
        r = fuzz.ratio(next(iter(ua)), next(iter(ub)))
        if r >= 70 and fuzz.token_sort_ratio(" ".join(wa), " ".join(wb)) >= 85:
            return "typo", round(r * 0.9, 1) + price_bonus
    return None


async def load_groups(session) -> dict[int, GroupInfo]:
    """Every perfume group that holds products, with what classify() needs."""
    rows = (await session.execute(text("""
        SELECT p.group_id, g.name, p.search_term, p.brand, p.volume, p.last_price
        FROM product p JOIN productgroup g ON g.id = p.group_id
        WHERE p.card_type = 'perfume' AND g.merged_into_id IS NULL
    """))).all()
    # Normalizing ~16k names takes ~20 s of CPU: off the event loop, so the
    # API keeps answering while an admin's "search again" runs.
    return await asyncio.to_thread(_build_groups, rows)


def _build_groups(rows) -> dict[int, GroupInfo]:
    raw: dict[int, dict] = {}
    for gid, gname, shop, brand, volume, price in rows:
        g = raw.setdefault(gid, {"name": gname, "shops": set(), "brands": Counter(), "vols": {}, "n": 0})
        g["shops"].add(shop)
        g["n"] += 1
        if brand:
            g["brands"][brand] += 1
        if volume and price:
            v = volume.lower().replace(" ", "")
            g["vols"][v] = min(float(price), g["vols"].get(v, float("inf")))
    groups: dict[int, GroupInfo] = {}
    for gid, g in raw.items():
        shop_brand = g["brands"].most_common(1)[0][0] if g["brands"] else None
        norm = perfume_normalizer.extract_all(g["name"], explicit_brand=shop_brand)
        brand = canonical_brand(norm["brand"] or shop_brand) or ""
        groups[gid] = GroupInfo(
            id=gid, name=g["name"], brand=brand, bkey=brand_key(brand),
            conc=(norm["concentration"] or "").lower(), key=name_key(norm["clean_name"], brand),
            shops=g["shops"], vols=g["vols"], products=g["n"],
        )
    return groups


def candidate_pairs(groups: dict[int, GroupInfo]) -> list[tuple[GroupInfo, GroupInfo, str, float]]:
    """Pairs of groups of one brand, sold in different shops, that classify()
    takes for one perfume. A is the group that stays (more shops, then more
    products, then the older one)."""
    by_brand: dict[str, list[GroupInfo]] = defaultdict(list)
    for g in groups.values():
        if g.bkey:
            by_brand[g.bkey].append(g)
    out = []
    for gs in by_brand.values():
        for i, a in enumerate(gs):
            for b in gs[i + 1:]:
                if a.shops & b.shops:
                    continue  # one shop sells both: two products, not two names of one
                verdict = classify(a, b)
                if verdict:
                    keep, other = sorted((a, b), key=lambda g: (-len(g.shops), -g.products, g.id))
                    out.append((keep, other, *verdict))
    # A short name that is inside two or more longer names ("Xerjoff 1888" in
    # "1888 Mefisto", "1888 Regio", ...) can't tell which one it is: skip it.
    shorter: Counter = Counter()
    for a, b, reason, _ in out:
        if reason == "subset":
            shorter[min((a, b), key=lambda g: len(g.key["words"])).id] += 1
    return [p for p in out if p[2] != "subset"
            or shorter[min(p[:2], key=lambda g: len(g.key["words"])).id] < 2]


async def find_pairs(session) -> dict:
    """Store new possible duplicates as pending pairs; drop pending pairs that
    no longer qualify. Pairs decided before (by ids or by names) are skipped."""
    groups = await load_groups(session)
    found = candidate_pairs(groups)
    existing = (await session.execute(select(GroupPair))).scalars().all()
    known_ids = {frozenset((p.group_a_id, p.group_b_id)) for p in existing if p.group_a_id and p.group_b_id}
    known_names = {frozenset((p.name_a.lower(), p.name_b.lower())) for p in existing}
    still = {frozenset((a.id, b.id)) for a, b, _, _ in found}
    dropped = 0
    for p in existing:
        if p.status == "pending" and frozenset((p.group_a_id, p.group_b_id)) not in still:
            await session.delete(p)
            dropped += 1
    added = 0
    for a, b, reason, score in found:
        if frozenset((a.id, b.id)) in known_ids or frozenset((a.name.lower(), b.name.lower())) in known_names:
            continue
        session.add(GroupPair(group_a_id=a.id, group_b_id=b.id, name_a=a.name[:255], name_b=b.name[:255],
                              reason=reason, score=score))
        added += 1
    await session.flush()
    logger.info(f"possible duplicates: {added} new, {dropped} no longer apply, {len(found)} found")
    return {"found": len(found), "added": added, "dropped": dropped}


async def merge_pair(session, pair: GroupPair, user_id: Optional[int]) -> int:
    """Move B's products into A; B stays as an empty group pointing to A, so new
    products that match B's name land in A. Returns the number moved."""
    if pair.status != "pending" or not pair.group_a_id or not pair.group_b_id:
        raise ValueError("this pair can no longer be merged")
    a = await session.get(ProductGroup, pair.group_a_id)
    b = await session.get(ProductGroup, pair.group_b_id)
    if a is None or b is None or a.merged_into_id or b.merged_into_id:
        raise ValueError("one of the groups is gone or already merged")
    moved = list((await session.execute(select(Product.id).where(Product.group_id == b.id))).scalars())
    await session.execute(update(Product).where(Product.group_id == b.id).values(group_id=a.id))
    b.merged_into_id = a.id
    pair.status, pair.moved_product_ids = "merged", moved
    pair.decided_at, pair.decided_by = datetime.utcnow(), user_id
    # Other open pairs with B are about a group that no longer holds products;
    # the next search proposes them again with A where they still apply.
    others = (await session.execute(select(GroupPair).where(
        GroupPair.status == "pending", GroupPair.id != pair.id,
        or_(GroupPair.group_a_id == b.id, GroupPair.group_b_id == b.id)))).scalars().all()
    for o in others:
        await session.delete(o)
    await session.flush()
    return len(moved)


async def keep_apart(session, pair: GroupPair, user_id: Optional[int]) -> None:
    if pair.status != "pending":
        raise ValueError("this pair is already decided")
    pair.status, pair.decided_at, pair.decided_by = "different", datetime.utcnow(), user_id
    await session.flush()


async def undo_merge(session, pair: GroupPair, user_id: Optional[int]) -> int:
    """Give B its products back: the ones the merge moved, and the ones that
    came later with a name that is B's and not A's."""
    if pair.status != "merged":
        raise ValueError("this pair is not merged")
    a = await session.get(ProductGroup, pair.group_a_id) if pair.group_a_id else None
    b = await session.get(ProductGroup, pair.group_b_id) if pair.group_b_id else None
    if a is None or b is None:
        raise ValueError("one of the groups is gone (a regroup ran); merge them again by hand if needed")
    back = set(pair.moved_product_ids or [])
    later = (await session.execute(select(Product).where(
        Product.group_id == a.id, Product.created_at > (pair.decided_at or datetime.min)))).scalars().all()
    if later:
        def key_of(name: str, brand: Optional[str]) -> dict:
            n = perfume_normalizer.extract_all(name, explicit_brand=brand)
            return name_key(n["clean_name"], n["brand"])
        for p in later:
            k = key_of(p.title, p.brand)
            if names_match(k, key_of(b.name, p.brand)) and not names_match(k, key_of(a.name, p.brand)):
                back.add(p.id)
    if back:
        await session.execute(update(Product).where(Product.group_id == a.id, Product.id.in_(back))
                              .values(group_id=b.id))
    b.merged_into_id = None
    pair.status, pair.decided_at, pair.decided_by = "undone", datetime.utcnow(), user_id
    await session.flush()
    return len(back)


_VOLUME_ORDER = re.compile(r"(\d+(?:[.,]\d+)?)")


def volume_sort_key(v: str) -> tuple:
    m = _VOLUME_ORDER.search(v or "")
    return (float(m.group(1).replace(",", ".")) if m else 1e9, v or "")
