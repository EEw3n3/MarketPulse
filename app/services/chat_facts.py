"""Facts for the AI chat: the server finds the perfume and the prices, the
model only words the answer (app/services/chat_answer.py).

Everything here is plain database work, no model calls:

- find_lines(): a question's brand + name -> the perfume lines (ProductGroups)
  it names, with the same brand_key / name_key / names_match rules the
  matcher uses for the catalogue, so "Sauvage" never brings in "Eau Sauvage".
- offers: one price per shop for a line and size, from the same rows the
  product page shows (in stock, priced) and seen in the last OFFER_MAX_AGE.
- deals: market.deals(), the list Today shows.
- history: real price readings only (the synthetic gap-fill rows of
  2026-10-07..21 are never quoted as prices someone could have paid).

Every builder returns a Facts object: a short plain-text block for the model,
the numbers and shops the answer may mention, and a template answer used when
the model fails or invents something.
"""
from __future__ import annotations

import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from statistics import median
from typing import Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from thefuzz import fuzz

from app.domain.models import Favorite, PriceHistory, Product
from app.services import market
from app.services.normalizer import (
    _same_word,
    brand_key,
    canonical_brand,
    is_placeholder_brand,
    name_key,
    names_match,
    strip_leading_brand,
)

# A listing not seen by a scan for this long is not quoted as a current price.
# The Notino and 220.lv prices come from the PC, which can skip a night or two.
OFFER_MAX_AGE = timedelta(days=4)
# Shops the chat knows by name -> Product.search_term.
STORES = {
    "notino": "notino.lv", "douglas": "douglas.lv", "makeup": "makeup.lv", "220": "220.lv",
}
STORE_LABEL = {"notino.lv": "Notino", "douglas.lv": "Douglas", "makeup.lv": "Makeup.lv", "220.lv": "220.lv"}
CONCENTRATIONS = ("EDT", "EDP", "Parfum", "EDC")
# Words a shop adds to a name that do not make it another perfume
# ("Tom Ford Private Blend Oud Wood" = "Oud Wood").
SOFT_WORDS = {"private", "blend", "limited", "edition", "collector", "collectors", "new", "original"}
# A member-only price is not something every buyer pays.
MEMBER_CODES = {"220.lv PLUS"}


def _fold_text(text: str) -> str:
    """Lowercase ASCII ("Hermès d´Orange" -> "hermes dorange")."""
    from app.services.normalizer import _fold
    return _fold(text or "")


def store_label(search_term: str) -> str:
    return STORE_LABEL.get((search_term or "").lower(), search_term or "")


def norm_store(name: Optional[str]) -> Optional[str]:
    """'Notino', 'notino.lv', 'нотино' -> 'notino.lv'."""
    if not name:
        return None
    s = name.lower().strip()
    s = {"нотино": "notino", "дуглас": "douglas", "мейкап": "makeup", "макияж": "makeup"}.get(s, s)
    s = s.removesuffix(".lv").strip()
    return STORES.get(s)


def ml_of(volume: Optional[str]) -> Optional[float]:
    m = re.match(r"\s*(\d+(?:[.,]\d+)?)\s*ml", (volume or "").lower())
    return float(m.group(1).replace(",", ".")) if m else None


def fmt_ml(v: Optional[float]) -> str:
    if v is None:
        return ""
    return f"{int(v)} ml" if float(v).is_integer() else f"{v:g} ml"


def eur(v: float) -> str:
    return f"€{v:.2f}"


@dataclass
class Facts:
    """What the answer may say."""
    kind: str
    lines: list[str] = field(default_factory=list)  # plain-text facts for the model
    template: dict = field(default_factory=dict)  # data for the template answer
    numbers: set[str] = field(default_factory=set)  # every number the answer may use
    stores: set[str] = field(default_factory=set)  # shop labels the answer may name
    chips: list[str] = field(default_factory=list)  # follow-up questions, user's language
    found: bool = True

    def allow(self, *values) -> None:
        for v in values:
            if v is None:
                continue
            if isinstance(v, float):
                self.numbers.update({f"{v:.2f}", f"{v:g}", f"{v:.1f}", f"{v:.0f}", str(round(v))})
            else:
                self.numbers.add(str(v))

    def text(self) -> str:
        return "\n".join(self.lines + ["(MarketPulse tracks four shops: Notino, Douglas, Makeup.lv, 220.lv.)"])


# ---------------------------------------------------------------------------
# Brands

_brand_cache: tuple[float, dict[str, list[str]]] = (0.0, {})


async def brand_index(db: AsyncSession) -> dict[str, list[str]]:
    """brand_key -> every spelling of that brand in the database."""
    global _brand_cache
    if time.time() - _brand_cache[0] < 900 and _brand_cache[1]:
        return _brand_cache[1]
    rows = (await db.execute(select(Product.brand).where(Product.brand.isnot(None)).distinct())).scalars().all()
    idx: dict[str, list[str]] = defaultdict(list)
    for b in rows:
        if b and not is_placeholder_brand(b):
            idx[brand_key(b)].append(b)
    _brand_cache = (time.time(), dict(idx))
    return _brand_cache[1]


async def resolve_brand(db: AsyncSession, brand: Optional[str]) -> Optional[str]:
    """A brand as typed (any case, alias, small typo) -> its brand_key, or None."""
    if not brand:
        return None
    idx = await brand_index(db)
    key = brand_key(brand)
    if key in idx:
        return key
    best, score = None, 0
    for k in idx:
        s = fuzz.ratio(key, k)
        if s > score:
            best, score = k, s
    return best if score >= 85 and len(key) >= 4 else None


async def find_brand_span(db: AsyncSession, words: list[str], skip: frozenset = frozenset()) -> tuple[Optional[str], int, int]:
    """(brand_key, start, length) of the first brand named in a list of words:
    the earliest position wins, then the longest name there ("armani acqua di
    gio" is Armani, not Acqua di Parma). A typo in a brand of 5+ letters is
    forgiven ("Chanell", "Versache", "Rabane")."""
    idx = await brand_index(db)
    keys = [k for k in idx if len(k) >= 5]
    for i in range(len(words)):
        for n in (4, 3, 2, 1):
            if i + n > len(words):
                continue
            key = brand_key(" ".join(words[i:i + n]))
            if len(key) >= 2 and key in idx and not (n == 1 and len(key) <= 2 and key not in {"ck", "dg"}):
                return key, i, n
        for n in (2, 1):
            if i + n > len(words) or any(w in skip or not w.isalpha() for w in words[i:i + n]):
                continue
            key = brand_key(" ".join(words[i:i + n]))
            if len(key) < 5:
                continue
            best, score = None, 0
            for k in keys:
                if abs(len(k) - len(key)) > 2:
                    continue
                sc = fuzz.ratio(key, k)
                if sc > score:
                    best, score = k, sc
            if best and score >= 86:
                return best, i, n
    return None, 0, 0


async def find_brand_in_text(db: AsyncSession, message: str) -> tuple[Optional[str], list[str]]:
    """(brand_key, the words that named it) for a brand anywhere in the message."""
    words = re.findall(r"[\w&'.-]+", message.lower())
    key, i, n = await find_brand_span(db, words)
    return key, words[i:i + n] if key else []


# ---------------------------------------------------------------------------
# Lines (one perfume in one concentration = one ProductGroup)

@dataclass
class Line:
    key: str  # "g<id>" or "p<id>" for a product without a group
    brand: str
    name: str  # without brand, volume and concentration
    concentration: Optional[str]
    products: list[Product]
    exact: bool = True

    @property
    def label(self) -> str:
        conc = f" {self.concentration}" if self.concentration else ""
        return f"{self.brand} {self.name}{conc}".strip()


_VOLUME_TAIL = re.compile(r"\s+\d+(?:[.,]\d+)?\s?(?:ml|g)\b.*$", re.IGNORECASE)


def product_name(p: Product) -> str:
    """'Dior Sauvage 100ml' -> 'Sauvage'."""
    title = (p.title or "").strip()
    for b in filter(None, {p.brand or "", canonical_brand(p.brand) or ""}):
        if title.lower().startswith(b.lower()):
            title = title[len(b):].strip(" -·")
            break
    title = _VOLUME_TAIL.sub("", title).strip()
    # "Joop! Joop Homme" -> "Homme"; a name that is only the brand stays.
    title = strip_leading_brand(title, {brand_key(p.brand)}) or title
    return re.sub(r"\s+", " ", title)


def _words(name: str, brand: Optional[str]) -> list[str]:
    return name_key(name, brand)["words"]


def _covers(query_words: list[str], words: list[str]) -> bool:
    """Every word of the question appears in the name (typos forgiven)."""
    return all(any(_same_word(q, w) for w in words) for q in query_words)


async def find_lines(
    db: AsyncSession,
    brand_k: Optional[str],
    name: Optional[str],
    *,
    include_sets: bool = False,
) -> tuple[list[Line], list[Line]]:
    """(exact lines, close lines) for a brand and a perfume name.

    Exact: the name has the same words as the question (names_match), or only
    SOFT_WORDS more. Close: the name holds every word of the question and more
    ("Sauvage" -> "Sauvage Elixir", "Eau Sauvage"); shown as suggestions only.
    """
    idx = await brand_index(db)
    spellings = idx.get(brand_k or "", [])
    stmt = select(Product).where(Product.last_price.isnot(None))
    if not include_sets:
        stmt = stmt.where(Product.card_type == "perfume")
    if spellings:
        stmt = stmt.where(Product.brand.in_(spellings))
    elif name:
        # No brand: the name words must all be in the title.
        words = [w for w in re.findall(r"\w+", name.lower()) if len(w) >= 2]
        if not words:
            return [], []
        stmt = stmt.where(*[Product.title.ilike(f"%{w}%") for w in words[:4]])
    else:
        return [], []
    products = (await db.execute(stmt.limit(3000))).scalars().all()

    by_line: dict[str, list[Product]] = defaultdict(list)
    for p in products:
        by_line[f"g{p.group_id}" if p.group_id else f"p{p.id}"].append(p)

    exact: list[Line] = []
    close: list[Line] = []
    for key, items in by_line.items():
        items.sort(key=lambda p: (p.title == (p.title or "").upper(), -(p.last_seen or datetime.min).timestamp()))
        first = items[0]
        line = Line(
            key=key,
            brand=canonical_brand(first.brand) or first.brand or "",
            name=product_name(first),
            concentration=first.concentration or None,
            products=items,
        )
        if not name:
            exact.append(line)
            continue
        lk = name_key(line.name, first.brand)
        # The question's words without this listing's brand words ("Al Wataniah
        # Attar Al Wesal" vs brand "Al Wataniah Khususi" -> attar, wesal).
        q = name_key(name, first.brand)
        q_words = q["words"]
        if names_match(q, lk):
            exact.append(line)
            continue
        words = lk["words"]
        hard_extra = [w for w in words if w not in SOFT_WORDS and not any(_same_word(w, x) for x in q_words)]
        if q_words and _covers(q_words, words):
            if not hard_extra:
                exact.append(line)
            else:
                line.exact = False
                close.append(line)
    close.sort(key=lambda ln: (len(_words(ln.name, ln.brand)), -len(ln.products)))
    return exact, close


async def locate(db: AsyncSession, q) -> tuple[list[Line], list[Line], bool]:
    """(exact, close, brand known) for the perfume of a question. When the
    brand + name finds nothing, try the brand written in the message, then the
    name words in titles of any brand (the model may name a parent brand)."""
    brand_k = await resolve_brand(db, q.brand)
    exact, close = await find_lines(db, brand_k, q.name)
    if exact or not q.name:
        return exact, close, brand_k is not None
    raw = getattr(q, "raw", "") or ""
    bk2, _ = await find_brand_in_text(db, raw) if raw else (None, [])
    if bk2 and bk2 != brand_k:
        e2, c2 = await find_lines(db, bk2, q.name)
        if e2:
            return e2, c2, True
    if bk2:
        # The user named a brand we track: do not answer with another brand.
        return exact, close, True
    e3, c3 = await find_lines(db, None, q.name)
    if e3 and len({ln.brand for ln in e3}) <= 2:
        return e3, c3, True
    return exact, close or c3, brand_k is not None


# ---------------------------------------------------------------------------
# Offers

@dataclass
class Offer:
    store: str  # search_term
    price: float  # the shop's regular price
    promo_price: Optional[float]
    promo_code: Optional[str]
    volume_ml: Optional[float]
    concentration: Optional[str]
    checked: datetime
    product_id: int
    line_label: str

    @property
    def pay(self) -> float:
        """What anyone pays: a public promo code counts, a members-only price does not."""
        if self.promo_price and self.promo_code not in MEMBER_CODES and 0 < self.promo_price < self.price:
            return self.promo_price
        return self.price

    @property
    def per_ml(self) -> Optional[float]:
        return self.pay / self.volume_ml if self.volume_ml else None


def offers_for(
    lines: list[Line],
    *,
    volume_ml: Optional[float] = None,
    concentration: Optional[str] = None,
    store: Optional[str] = None,
    now: Optional[datetime] = None,
) -> tuple[list[Offer], list[Product]]:
    """(current offers, tracked-but-unavailable products) of the lines.

    One offer per shop, size and line: the cheapest listing (a shop can list
    one bottle twice). Unavailable = sold out or not seen for OFFER_MAX_AGE.
    """
    now = now or datetime.utcnow()
    fresh = now - OFFER_MAX_AGE
    best: dict[tuple, Offer] = {}
    gone: list[Product] = []
    for line in lines:
        if concentration and (line.concentration or "").lower() != concentration.lower():
            continue
        for p in line.products:
            if store and (p.search_term or "").lower() != store:
                continue
            ml = ml_of(p.volume)
            if volume_ml and (ml is None or abs(ml - volume_ml) > 0.6):
                continue
            price = float(p.last_price or 0)
            if not p.is_available or price <= 0 or (p.last_seen or datetime.min) < fresh:
                gone.append(p)
                continue
            o = Offer(
                store=(p.search_term or "").lower(), price=price,
                promo_price=float(p.promo_price) if p.promo_price else None, promo_code=p.promo_code,
                volume_ml=ml, concentration=line.concentration, checked=p.last_seen,
                product_id=p.id, line_label=line.label,
            )
            k = (line.key, o.store, ml)
            if k not in best or o.pay < best[k].pay:
                best[k] = o
    offers = sorted(best.values(), key=lambda o: (o.pay, o.store))
    return offers, gone


def _offer_line(o: Offer, f: Facts, with_name: bool = True) -> str:
    name = f"{o.line_label} {fmt_ml(o.volume_ml)}".strip() if with_name else fmt_ml(o.volume_ml)
    s = f"- {name}: {store_label(o.store)} {eur(o.price)}"
    f.allow(o.price, o.volume_ml)
    if o.promo_price and 0 < o.promo_price < o.price:
        if o.promo_code in MEMBER_CODES:
            s += f" (members-only price {eur(o.promo_price)} with {o.promo_code})"
        else:
            code = f" with code \"{o.promo_code}\"" if o.promo_code else ""
            s += f" (promo {eur(o.promo_price)}{code})"
        f.allow(o.promo_price)
        f.numbers.add("220")
    s += f", in stock, checked {o.checked:%d.%m.%Y}"
    f.stores.add(store_label(o.store))
    return s


# ---------------------------------------------------------------------------
# Builders. Each returns Facts; `q` is the parsed question (chat_answer.Query).

def _not_found(q, close: list[Line], brand_known: bool) -> Facts:
    f = Facts(kind="not_found", found=False)
    name = q.name.title() if q.name and q.name == q.name.lower() else q.name
    asked = " ".join(filter(None, [q.brand, name, q.concentration, fmt_ml(q.volume_ml)]))
    f.lines.append(f"The perfume the user asked about ({asked}) is NOT in the MarketPulse database.")
    if close:
        names = []
        for ln in close[:3]:
            if ln.label not in names:
                names.append(ln.label)
        f.lines.append("Similar perfumes that ARE tracked (other perfumes, not the one asked): " + "; ".join(names))
        f.chips = names[:3]
    elif not brand_known and q.brand:
        f.lines.append(f"The brand {q.brand} is not tracked at all.")
    f.template = {"asked": asked, "similar": f.chips, "brand": q.brand if brand_known else None}
    return f


async def price_facts(db: AsyncSession, q, now: Optional[datetime] = None) -> Facts:
    """Where a perfume is sold and for how much (also "where is it cheaper")."""
    exact, close, brand_known = await locate(db, q)
    if not exact:
        return _not_found(q, close, brand_known)
    store = norm_store(q.store)
    offers, gone = offers_for(exact, volume_ml=q.volume_ml, concentration=q.concentration, store=store, now=now)
    f = Facts(kind="price")
    asked = " ".join(filter(None, [exact[0].brand, exact[0].name, q.concentration, fmt_ml(q.volume_ml)]))
    where = f" at {store_label(store)}" if store else ""
    if not offers and store:
        # Not in the shop the user named: the same bottle elsewhere is the useful answer.
        elsewhere, _ = offers_for(exact, volume_ml=q.volume_ml, concentration=q.concentration, now=now)
        if elsewhere:
            f.lines.append(f"{asked} is NOT sold at {store_label(store)} now. Other shops have it, cheapest first:")
            for o in elsewhere[:5]:
                f.lines.append(_offer_line(o, f))
            f.stores.add(store_label(store))
            f.template = {"asked": asked, "elsewhere": elsewhere[:5], "store": store_label(store)}
            return f
    if not offers:
        f.found = bool(gone)
        if gone:
            last = max(gone, key=lambda p: p.last_seen or datetime.min)
            f.lines.append(f"{asked}{where} is tracked but NOT available now (sold out or not listed by the shop).")
            lp = float(last.last_price or 0)
            if lp > 0:
                f.lines.append(f"Last seen: {store_label(last.search_term)} {eur(lp)} on {last.last_seen:%d.%m.%Y}.")
                f.allow(lp, last.last_seen.strftime("%Y-%m-%d"))
                f.stores.add(store_label(last.search_term))
            f.template = {"asked": asked, "gone": True, "last": (store_label(last.search_term), lp, last.last_seen)}
        else:
            # The line exists but not in this size / concentration / shop.
            others, _ = offers_for(exact, concentration=q.concentration, store=store, now=now)
            others = others or offers_for(exact, now=now)[0]
            f.lines.append(f"{asked}{where} is not sold now in the tracked shops.")
            if others:
                f.lines.append("What IS available of this perfume (other size, concentration or shop):")
                for o in _one_per_size(others)[:5]:
                    f.lines.append(_offer_line(o, f))
            f.template = {"asked": asked, "missing": True, "others": _one_per_size(others)[:5]}
        f.found = True
        return f

    sizes = sorted({o.volume_ml for o in offers if o.volume_ml})
    concs = sorted({o.concentration or "" for o in offers})
    multi = len(sizes) > 1 or len(concs) > 1
    if not multi:
        f.lines.append(f"Current prices for {offers[0].line_label} {fmt_ml(offers[0].volume_ml)}{where}, cheapest first:")
        for o in offers[:6]:
            f.lines.append(_offer_line(o, f, with_name=False))
        if len(offers) > 1:
            diff = offers[-1].pay - offers[0].pay
            f.lines.append(f"Difference between the cheapest and the dearest shop: {eur(diff)}.")
            f.allow(diff)
    else:
        f.lines.append(
            f"The user did not name one size/concentration. Cheapest shop for each size of {asked}{where}:")
        for o in _one_per_size(offers)[:8]:
            f.lines.append(_offer_line(o, f))
    f.template = {"offers": offers if not multi else _one_per_size(offers)[:8], "multi": multi}
    if close:
        f.lines.append("Related but different perfumes (mention only if useful): "
                       + "; ".join(dict.fromkeys(ln.label for ln in close[:3])))
    f.lines.append(f"Only these shops have it now: {', '.join(sorted({store_label(o.store) for o in offers}))}; "
                   f"the other tracked shops do not.")
    return f


def _one_per_size(offers: list[Offer]) -> list[Offer]:
    """The cheapest offer for each (concentration, size), smallest size first."""
    best: dict[tuple, Offer] = {}
    for o in offers:
        k = (o.line_label, o.volume_ml)
        if k not in best or o.pay < best[k].pay:
            best[k] = o
    return sorted(best.values(), key=lambda o: (o.line_label, o.volume_ml or 0))


async def compare_facts(db: AsyncSession, q, now: Optional[datetime] = None) -> Facts:
    """Two perfumes (or two sizes) side by side, with the price per ml."""
    f = Facts(kind="compare")
    rows = []
    found = []
    for item in q.items[:3]:
        brand_k = await resolve_brand(db, item.get("brand") or q.brand)
        exact, _ = await find_lines(db, brand_k, item.get("name"))
        conc = item.get("concentration")
        vol = item.get("volume_ml")
        offers, _ = offers_for(exact, volume_ml=vol, concentration=conc, now=now) if exact else ([], [])
        label = " ".join(filter(None, [item.get("brand") or q.brand, item.get("name"), conc, fmt_ml(vol)]))
        found.append((label, offers))
    # Like for like: big bottles are cheaper per ml, so compare one size both have
    # (the one closest to 100 ml) when the user named no size.
    common = None
    if all(o for _, o in found) and not any(i.get("volume_ml") for i in q.items[:3]):
        sizes = set.intersection(*[{o.volume_ml for o in offers if o.volume_ml} for _, offers in found])
        if sizes:
            common = min(sizes, key=lambda v: abs(v - 100))
    if common:
        f.lines.append(f"Both are sold in {fmt_ml(common)}; compared at that size.")
        f.allow(common)
    for label, offers in found:
        if common:
            offers = [o for o in offers if o.volume_ml == common]
        if not offers:
            f.lines.append(f"- {label}: not available in the tracked shops now.")
            rows.append((label, None))
            continue
        best = min(offers, key=lambda o: o.per_ml or o.pay)
        f.lines.append(_offer_line(best, f) + (f", {eur(best.per_ml)}/ml" if best.per_ml else ""))
        if best.per_ml:
            f.allow(best.per_ml, round(best.per_ml, 2))
        rows.append((label, best))
    f.lines.insert(0, "Cheapest offer of each perfume the user compares (by price per ml):")
    f.template = {"rows": rows}
    f.found = any(r[1] for r in rows)
    return f


async def deals_facts(db: AsyncSession, q, lang: str) -> Facts:
    """'What got cheaper this week' = the Today list, same rules."""
    store = norm_store(q.store)
    brand = None
    if q.brand:
        brand_k = await resolve_brand(db, q.brand)
        brand = canonical_brand(brand_k) if brand_k else q.brand
    items = await market.deals(db, days=7, limit=4, stores=[store] if store else None,
                               brands=[brand] if brand else None)
    f = Facts(kind="deals")
    scope = " ".join(filter(None, [brand, f"at {store_label(store)}" if store else ""]))
    if not items:
        f.lines.append(f"No confirmed price cuts {scope} in the last 7 days (a cut counts when the price is "
                       f"at least 5% under its usual 30-day price and the shop page confirmed it).")
        f.template = {"items": [], "scope": scope, "brand": brand, "store": store_label(store) if store else None}
        return f
    f.lines.append(f"Biggest confirmed price cuts {scope} in the last 7 days, vs the usual 30-day price "
                   f"(the same list as the Today page):")
    for it in items:
        vol = fmt_ml(ml_of(it.volume))
        name = " ".join(filter(None, [canonical_brand(it.brand) or it.brand, it.name, it.concentration, vol]))
        old, new = float(it.old_price), float(it.new_price)
        pct = round(it.change_percent)
        shop = it.store_name
        f.lines.append(f"- {name}: {shop} now {eur(new)}, usually {eur(old)} ({pct}%)")
        f.allow(new, old, pct, abs(pct), ml_of(it.volume))
        f.stores.add(shop)
    f.template = {"items": items, "scope": scope, "brand": brand, "store": store_label(store) if store else None}
    return f


async def history_facts(db: AsyncSession, q, now: Optional[datetime] = None) -> Facts:
    """How the price of one perfume and size moved: real readings only."""
    exact, close, brand_known = await locate(db, q)
    if not exact:
        return _not_found(q, close, brand_known)
    lines = [ln for ln in exact if not q.concentration or (ln.concentration or "").lower() == q.concentration.lower()]
    ids = [p.id for ln in lines for p in ln.products
           if not q.volume_ml or (ml_of(p.volume) and abs(ml_of(p.volume) - q.volume_ml) <= 0.6)]
    store = norm_store(q.store)
    by_id = {p.id: p for ln in lines for p in ln.products}
    if store:
        ids = [i for i in ids if (by_id[i].search_term or "").lower() == store]
    f = Facts(kind="history")
    label = " ".join(filter(None, [exact[0].brand, exact[0].name, q.concentration, fmt_ml(q.volume_ml)]))
    if not ids:
        f.found = False
        f.lines.append(f"{label}: no listings of this size/concentration are tracked.")
        f.template = {"label": label, "rows": []}
        return f
    start = q.date_from or date(2026, 10, 1)
    end = q.date_to or (now or datetime.utcnow()).date()
    hist = (await db.execute(
        select(PriceHistory.product_id, PriceHistory.price, PriceHistory.parsed_at)
        .where(PriceHistory.product_id.in_(ids), PriceHistory.change_type != "synthetic",
               PriceHistory.in_stock.is_(True), PriceHistory.price > 0,
               PriceHistory.parsed_at >= datetime.combine(start, datetime.min.time()),
               PriceHistory.parsed_at < datetime.combine(end + timedelta(days=1), datetime.min.time()))
        .order_by(PriceHistory.parsed_at)
    )).all()
    offers, _ = offers_for(lines, volume_ml=q.volume_ml, store=store, now=now)
    f.lines.append(f"Real price readings of {label} from {start:%d.%m.%Y} to {end:%d.%m.%Y} (shop scans; days without a "
                   f"reading are not counted):")
    rows = []
    per_store: dict[str, list] = defaultdict(list)
    for pid, price, at in hist:
        per_store[(by_id[pid].search_term or "").lower()].append((float(price), at, by_id[pid]))
    for st, items in sorted(per_store.items()):
        lo = min(items, key=lambda x: x[0])
        hi = max(items, key=lambda x: x[0])
        vol = fmt_ml(ml_of(lo[2].volume))
        f.lines.append(f"- {store_label(st)} {vol} {lo[2].concentration or ''}: lowest {eur(lo[0])} on "
                       f"{lo[1]:%d.%m.%Y}, highest {eur(hi[0])} on {hi[1]:%d.%m.%Y}, {len(items)} readings")
        f.allow(lo[0], hi[0], lo[1].strftime("%Y-%m-%d"), hi[1].strftime("%Y-%m-%d"), lo[1].day, hi[1].day, len(items))
        f.stores.add(store_label(st))
        rows.append((store_label(st), vol, lo, hi))
    if not hist:
        f.lines.append("- no real price readings in this period.")
    if offers:
        f.lines.append("Current prices:")
        for o in offers[:5]:
            f.lines.append(_offer_line(o, f))
    verdict = None
    if hist and offers:
        low = min(float(p) for _, p, _ in hist)
        now_best = min(o.price for o in offers)
        if low < now_best - 0.01:
            f.lines.append(f"Answer: yes, it was cheaper in this period: lowest {eur(low)} vs {eur(now_best)} now "
                           f"(regular prices).")
            verdict = ("cheaper", low, now_best)
        elif abs(low - now_best) <= 0.01:
            f.lines.append(f"Answer: no, it was not cheaper: the lowest price in this period ({eur(low)}) is the "
                           f"same as now.")
            verdict = ("same", low, now_best)
        else:
            f.lines.append(f"Answer: no, it is cheaper now ({eur(now_best)}) than at any time in this period "
                           f"(lowest then {eur(low)}).")
            verdict = ("now_cheaper", low, now_best)
    f.lines.append("Price history in MarketPulse starts in May 2026 for some shops; most readings are from "
                   "late October 2026 on.")
    f.allow(2026)
    f.template = {"label": label, "rows": rows, "offers": offers[:5], "start": start, "end": end, "verdict": verdict}
    return f


async def promo_facts(db: AsyncSession, q, now: Optional[datetime] = None) -> Facts:
    """Promo codes and member prices the scans saw."""
    now = now or datetime.utcnow()
    store = norm_store(q.store)
    stmt = (
        select(Product.search_term, Product.promo_code, func.count(), func.min(
            (Product.last_price - Product.promo_price) / Product.last_price * 100),
            func.max((Product.last_price - Product.promo_price) / Product.last_price * 100))
        .where(Product.promo_code.isnot(None), Product.is_available.is_(True), Product.promo_price > 0,
               Product.last_price > 0, Product.last_seen >= now - OFFER_MAX_AGE)
        .group_by(Product.search_term, Product.promo_code)
        .order_by(desc(func.count()))
    )
    if store:
        stmt = stmt.where(func.lower(Product.search_term) == store)
    rows = (await db.execute(stmt)).all()
    f = Facts(kind="promo")
    if not rows:
        f.lines.append(f"No promo codes seen{' at ' + store_label(store) if store else ''} in the latest scans.")
    for st, code, n, lo, hi in rows:
        lo, hi = round(float(lo)), round(float(hi))
        kind = "members-only price (220.lv PLUS membership), not a public code" if code in MEMBER_CODES \
            else f"promo code \"{code}\" entered at checkout"
        f.lines.append(f"- {store_label(st)}: {kind}; {n} perfumes, {lo}–{hi}% off the regular price")
        f.allow(n, lo, hi)
        f.stores.add(store_label(st))
    f.lines.append("Codes are read from the product pages during scans; the shop may end them any time.")
    f.template = {"rows": rows}
    if q.brand:
        # A code for one perfume: the price answer shows it per shop.
        pf = await price_facts(db, q, now=now)
        if pf.found:
            f.lines.append("For the perfume the user named:")
            f.lines.extend(pf.lines)
            f.numbers |= pf.numbers
            f.stores |= pf.stores
    return f


async def brand_facts(db: AsyncSession, q, lang: str, now: Optional[datetime] = None) -> Facts:
    """A broad question about a brand: how much of it is tracked, price range,
    the lines sold in the most shops."""
    brand_k = await resolve_brand(db, q.brand)
    if not brand_k:
        return _not_found(q, [], False)
    exact, _ = await find_lines(db, brand_k, None)
    store = norm_store(q.store)
    offers, _ = offers_for(exact, store=store, now=now)
    f = Facts(kind="brand")
    brand = exact[0].brand if exact else q.brand
    if not offers:
        f.lines.append(f"{brand}: tracked, but nothing in stock now{' at ' + store_label(store) if store else ''}.")
        f.template = {"brand": brand, "n": 0}
        return f
    by_line: dict[str, list[Offer]] = defaultdict(list)
    for o in offers:
        by_line[o.line_label].append(o)
    shops = sorted({store_label(o.store) for o in offers})
    lo, hi = min(o.pay for o in offers), max(o.pay for o in offers)
    f.lines.append(f"{brand}: {len(by_line)} perfumes (lines) in stock in {len(shops)} shops "
                   f"({', '.join(shops)}), bottles from {eur(lo)} to {eur(hi)}.")
    f.allow(len(by_line), len(shops), lo, hi)
    f.stores |= set(shops)
    top = sorted(by_line.items(), key=lambda kv: (-len({o.store for o in kv[1]}), min(o.pay for o in kv[1])))[:3]
    f.lines.append("Lines sold in the most shops, with their cheapest bottle:")
    for label, items in top:
        o = min(items, key=lambda o: o.pay)
        f.lines.append(_offer_line(o, f) + f" ({len({x.store for x in items})} shops)")
        f.allow(len({x.store for x in items}))
    f.chips = [label for label, _ in top[:3]]
    f.template = {"brand": brand, "n": len(by_line), "shops": shops, "lo": lo, "hi": hi,
                  "top": [(label, min(items, key=lambda o: o.pay)) for label, items in top]}
    return f


async def store_compare_facts(db: AsyncSession, q, now: Optional[datetime] = None) -> Facts:
    """'Which shop is cheapest for Chanel?': for each bottle sold in 2+ shops,
    which shop has it cheapest."""
    brand_k = await resolve_brand(db, q.brand)
    f = Facts(kind="store_compare")
    if not brand_k:
        return _not_found(q, [], False)
    exact, _ = await find_lines(db, brand_k, q.name)
    offers, _ = offers_for(exact, now=now)
    by_bottle: dict[tuple, list[Offer]] = defaultdict(list)
    for o in offers:
        by_bottle[(o.line_label, o.volume_ml)].append(o)
    wins: dict[str, int] = defaultdict(int)
    shared = 0
    for items in by_bottle.values():
        if len({o.store for o in items}) < 2:
            continue
        shared += 1
        wins[store_label(min(items, key=lambda o: o.pay).store)] += 1
    brand = exact[0].brand if exact else q.brand
    if not shared:
        f.lines.append(f"No {brand} bottle is sold in two or more tracked shops right now, so there is no "
                       f"shop-by-shop comparison.")
        f.template = {"brand": brand, "shared": 0}
        return f
    f.lines.append(f"{brand}: {shared} bottles (same perfume, concentration and size) are sold in 2+ shops. "
                   f"Cheapest shop for each of them:")
    for shop, n in sorted(wins.items(), key=lambda kv: -kv[1]):
        f.lines.append(f"- {shop}: cheapest for {n} of {shared} bottles")
        f.allow(n)
        f.stores.add(shop)
    f.allow(shared)
    f.template = {"brand": brand, "shared": shared, "wins": sorted(wins.items(), key=lambda kv: -kv[1])}
    return f


async def cheapest_facts(db: AsyncSession, q, now: Optional[datetime] = None) -> Facts:
    """The cheapest bottles in stock (full size: 30 ml and up unless asked)."""
    now = now or datetime.utcnow()
    store = norm_store(q.store)
    stmt = (
        select(Product)
        .where(Product.is_available.is_(True), Product.last_price > 0, Product.card_type == "perfume",
               Product.last_seen >= now - OFFER_MAX_AGE, Product.brand.isnot(None))
        .order_by(Product.last_price)
        .limit(400)
    )
    if store:
        stmt = stmt.where(func.lower(Product.search_term) == store)
    if q.brand:
        brand_k = await resolve_brand(db, q.brand)
        spellings = (await brand_index(db)).get(brand_k or "", [])
        if spellings:
            stmt = stmt.where(Product.brand.in_(spellings))
    if q.concentration:
        stmt = stmt.where(Product.concentration == q.concentration)
    rows = (await db.execute(stmt)).scalars().all()
    min_ml = q.volume_ml or 30
    picked = [p for p in rows if not is_placeholder_brand(p.brand)
              and (ml_of(p.volume) or 0) >= min_ml and (not q.volume_ml or abs((ml_of(p.volume) or 0) - q.volume_ml) <= 0.6)]
    f = Facts(kind="cheapest")
    f.lines.append(f"Cheapest perfumes in stock ({fmt_ml(min_ml)}{'' if q.volume_ml else ' and up'}"
                   f"{', ' + store_label(store) if store else ''}):")
    for p in picked[:5]:
        o = Offer(store=(p.search_term or "").lower(), price=float(p.last_price),
                  promo_price=float(p.promo_price) if p.promo_price else None, promo_code=p.promo_code,
                  volume_ml=ml_of(p.volume), concentration=p.concentration, checked=p.last_seen,
                  product_id=p.id, line_label=f"{canonical_brand(p.brand)} {product_name(p)} {p.concentration or ''}".strip())
        f.lines.append(_offer_line(o, f))
    f.found = bool(picked)
    f.template = {"rows": picked[:5]}
    return f


async def watchlist_facts(db: AsyncSession, user_id: int, now: Optional[datetime] = None) -> Facts:
    now = now or datetime.utcnow()
    rows = (await db.execute(
        select(Favorite, Product).join(Product, Product.id == Favorite.product_id)
        .where(Favorite.user_id == user_id).order_by(desc(Favorite.created_at)).limit(10)
    )).all()
    f = Facts(kind="watchlist")
    if not rows:
        f.lines.append("The user's watchlist (Favorites) is empty.")
        f.template = {"rows": []}
        return f
    f.lines.append("The user's watchlist (Favorites), newest first:")
    out = []
    for fav, p in rows:
        price = float(p.last_price or 0)
        added = float(fav.price_when_added) if fav.price_when_added else None
        live = p.is_available and price > 0 and (p.last_seen or datetime.min) >= now - OFFER_MAX_AGE
        name = f"{canonical_brand(p.brand)} {product_name(p)} {p.concentration or ''} {fmt_ml(ml_of(p.volume))}".strip()
        s = f"- {name}, {store_label(p.search_term)}: "
        s += f"{eur(price)} now" if live else "not available now"
        if added and live:
            pct = round((price - added) / added * 100)
            s += f", added at {eur(added)} ({pct:+d}%)"
            f.allow(added, pct, abs(pct))
        f.lines.append(s)
        f.allow(price)
        f.stores.add(store_label(p.search_term))
        out.append((name, store_label(p.search_term), price if live else None, added))
    f.template = {"rows": out}
    return f


async def product_facts(db: AsyncSession, product_id: int, now: Optional[datetime] = None) -> Optional[Facts]:
    """The perfume on the page the chat was opened from: current offers for its
    size plus how today's best price compares with the last 30 days."""
    now = now or datetime.utcnow()
    p = await db.get(Product, product_id)
    if not p:
        return None
    if p.group_id:
        group = (await db.execute(select(Product).where(Product.group_id == p.group_id))).scalars().all()
    else:
        group = [p]
    line = Line(key=f"g{p.group_id}" if p.group_id else f"p{p.id}",
                brand=canonical_brand(p.brand) or p.brand or "", name=product_name(p),
                concentration=p.concentration or None, products=list(group))
    vol = ml_of(p.volume)
    offers, _ = offers_for([line], volume_ml=vol, now=now)
    f = Facts(kind="product")
    label = f"{line.label} {fmt_ml(vol)}".strip()
    f.lines.append(f"The user is looking at the product page of {label}.")
    if not offers:
        f.lines.append("It is not available in any tracked shop right now.")
        f.template = {"label": label, "offers": []}
        return f
    f.lines.append("Current prices, cheapest first:")
    for o in offers[:5]:
        f.lines.append(_offer_line(o, f, with_name=False))
    ids = [x.id for x in group if vol is None or (ml_of(x.volume) and abs(ml_of(x.volume) - vol) <= 0.6)]
    # The history table records changes only, so a price that held for three
    # weeks is one row: rebuild the best price of each day (real readings only).
    days = [(now - timedelta(days=i)).date() for i in range(29, -1, -1)]
    rows = (await db.execute(
        select(PriceHistory.product_id, PriceHistory.price, PriceHistory.in_stock, PriceHistory.parsed_at)
        .where(PriceHistory.product_id.in_(ids), PriceHistory.change_type != "synthetic")
        .order_by(PriceHistory.product_id, PriceHistory.parsed_at)
    )).all()
    events: dict[int, list] = defaultdict(list)
    for pid, price, in_stock, at in rows:
        events[pid].append((at.date(), float(price) if in_stock and price and price > 0 else None))
    daily: list[Optional[float]] = []
    for d in days:
        vals = []
        for pid, evs in events.items():
            cur = None
            for day, price in evs:
                if day > d:
                    break
                cur = price
            if cur:
                vals.append(cur)
        daily.append(min(vals) if vals else None)
    covered = [v for v in daily if v]
    best = min(o.price for o in offers)
    if len(covered) >= 7:
        lo, med = min(covered), median(covered)
        f.lines.append(f"Best regular price of each day over the last 30 days ({len(covered)} days with data): "
                       f"lowest {eur(lo)}, typical (median) {eur(med)}. Today's best regular price: {eur(best)}.")
        if abs(lo - med) <= 0.01 and abs(best - med) <= 0.01:
            verdict = "flat"
            f.lines.append("The best price has not changed in the last 30 days: today's price is the usual one, "
                           "neither a discount nor a markup.")
        elif best <= lo + 0.01:
            verdict = "lowest"
            f.lines.append("Today's best price is the lowest of the last 30 days.")
        elif abs(best - med) <= 0.01:
            verdict = "usual"
            f.lines.append("Today's best price equals the typical price of the last 30 days: an ordinary price, "
                           "not a discount.")
        elif best < med - 0.01:
            verdict = "below"
            f.lines.append("Today's best price is below the typical price of the last 30 days.")
        else:
            verdict = "above"
            f.lines.append("Today's best price is not below the typical price of the last 30 days.")
        f.template = {"label": label, "offers": offers[:5], "lo": lo, "med": med, "verdict": verdict}
    else:
        f.lines.append("Too few days of real price data in the last 30 days to judge whether the price is good.")
        f.template = {"label": label, "offers": offers[:5], "verdict": None}
    return f
