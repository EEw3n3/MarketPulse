"""Chat endpoint — AI assistant powered by Gemini with real DB context."""
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, func, or_

from app.api import schemas
from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.rate_limit import limit
from app.domain.models import Favorite, Product
from app.services.ai_generator import ai_generator

router = APIRouter(prefix="/chat", tags=["chat"])


async def _build_favorites_block(db: AsyncSession, user_id: int) -> str:
    stmt = (
        select(Favorite, Product)
        .join(Product, Product.id == Favorite.product_id)
        .where(Favorite.user_id == user_id)
        .order_by(desc(Favorite.created_at))
        .limit(8)
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        return "No items in watchlist yet."
    lines = []
    for fav, prod in rows:
        added = (
            f" | added at €{float(fav.price_when_added):.2f}"
            if fav.price_when_added
            else ""
        )
        lines.append(
            f"• {prod.brand or ''} {prod.title} — "
            f"€{float(prod.last_price):.2f} ({prod.search_term}){added}"
        )
    return "\n".join(lines)


async def _build_drops_block(db: AsyncSession) -> str:
    week_ago = datetime.utcnow() - timedelta(days=7)
    stmt = (
        select(Product)
        .where(
            Product.old_price.isnot(None),
            Product.old_price > 0,
            Product.last_price > 0,
            Product.last_price < Product.old_price,
            Product.is_available.is_(True),
            Product.last_seen >= week_ago,
        )
        .order_by(
            desc(
                (Product.old_price - Product.last_price) / Product.old_price
            )
        )
        .limit(5)
    )
    products = (await db.execute(stmt)).scalars().all()
    if not products:
        return "No significant price drops found in the last 7 days."
    lines = []
    for p in products:
        pct = (
            (float(p.old_price) - float(p.last_price))
            / float(p.old_price)
            * 100
        )
        lines.append(
            f"• {p.brand or ''} {p.title}: "
            f"€{float(p.old_price):.2f}→€{float(p.last_price):.2f} "
            f"(−{pct:.1f}%) at {p.search_term}"
        )
    return "\n".join(lines)


_SEARCH_STOP = {
    # Russian — generic / interrogative / temporal / commerce
    "есть", "нету", "нет", "база", "базе", "базы", "нашей", "нашем", "наша",
    "магазин", "магазины", "магазинов", "цена", "цены", "ценам", "стоит",
    "стоят", "купить", "купи", "хочу", "хотел", "хотела", "парфюм", "парфюмы",
    "парфюма", "парфюмов", "духи", "духов", "запах", "запахом", "аромат",
    "ароматы", "ароматов", "самый", "самая", "самое", "самые", "дешевый",
    "дешевая", "дешево", "дешёвый", "дорогой", "дорого", "сколько", "какой",
    "какая", "какие", "какое", "сейчас", "сегодня", "завтра", "вчера",
    "наличии", "наличие", "наличия", "привет", "здравствуй", "здравствуйте",
    "пожалуйста", "скажи", "скажите", "расскажи", "покажи", "найди",
    "поиск", "только", "очень", "тоже", "также", "если", "когда", "тогда",
    "потом", "пока", "ещё", "еще", "уже", "тебя", "тебе", "меня", "мне",
    "нас", "вас", "что", "это", "этот", "эта", "эти", "тот", "тех", "таких",
    "там", "тут", "здесь", "везде", "нигде", "точно", "наверное", "может",
    "можно", "нельзя", "надо", "нужно", "будет", "была", "было", "были",
    # English
    "what", "have", "has", "does", "did", "the", "and", "any", "all", "some",
    "price", "prices", "for", "about", "with", "from", "find", "show", "list",
    "perfume", "perfumes", "fragrance", "brand", "brands", "store", "stores",
    "cheap", "cheapest", "best", "where", "which", "when", "now", "today",
    "tomorrow", "yesterday", "available", "stock", "hello", "please", "tell",
    "show", "give", "want", "need", "would", "could", "should", "buy",
    "this", "that", "these", "those", "your", "mine", "ours",
    # Latvian
    "cena", "cenas", "cenām", "lēts", "lēta", "labākais", "labākā", "kur",
    "vai", "mums", "tagad", "šodien", "rīt", "vakar", "noliktavā", "veikals",
    "veikalā", "lūdzu", "sveiki", "labdien", "smaržas", "smaržām",
    "kāds", "kāda", "kuru", "kuram", "ir", "var", "varbūt", "vajag",
}


_VOLUME_RE = re.compile(r'^\d+\.?\d*(ml|oz|мл|л)$', re.IGNORECASE)


def _is_volume_only_keyword(kw: str) -> bool:
    return bool(_VOLUME_RE.match(kw))


# Store names live in Product.search_term, not title/brand — exclude them from
# the text match so they don't act as dead/over-broad search terms.
_STORE_TOKENS = {
    "notino", "notino.lv", "douglas", "douglas.lv", "makeup", "makeup.lv",
    "220", "220.lv", "1a", "1a.lv",
}


def _extract_search_keywords(message: str) -> list[str]:
    """Extract content-bearing keywords (likely brand/product names) from a query."""
    keywords: list[str] = []
    seen: set[str] = set()
    for raw in message.lower().split():
        w = raw.strip(".,!?:;«»\"'()[]{}—–-/\\")
        if len(w) < 3 or w in _SEARCH_STOP or w.isdigit():
            continue
        if w in seen:
            continue
        seen.add(w)
        keywords.append(w)
    return keywords


def _resolve_context_keywords(
    keywords: list[str],
    history: list[schemas.ChatMessage],
) -> list[str]:
    """If current keywords are only volume tokens (e.g. '60ml'), resolve the
    brand/product name from recent conversation history so a follow-up like
    'А 60ml вариант есть?' correctly searches 'Dior Sauvage 60ml'."""
    if not keywords or not all(_is_volume_only_keyword(k) for k in keywords):
        return keywords
    for msg in reversed(history[-4:]):
        if msg.role == "user":
            hist_kw = [k for k in _extract_search_keywords(msg.content)
                       if not _is_volume_only_keyword(k)]
            if hist_kw:
                return hist_kw + keywords
    return keywords


def _format_search_results(products: list[Product], header: str) -> str:
    lines = [header]
    for p in products:
        avail = "in stock" if p.is_available else "OUT OF STOCK"
        price = float(p.last_price) if p.last_price else 0.0
        price_str = f"€{price:.2f}" if price > 0 else "price unknown"
        if p.promo_price and 0 < float(p.promo_price) < price:
            code = f" with code {p.promo_code}" if p.promo_code else ""
            price_str += f" (promo €{float(p.promo_price):.2f}{code})"
        conc = f" {p.concentration}" if p.concentration else ""
        lines.append(
            f"• {p.brand or ''} {p.title}{conc} — "
            f"{price_str} at {p.search_term} ({avail})"
        )
    return "\n".join(lines)


# Rows not seen by a scan for this long are left over from removed listings.
_FRESH_DAYS = 7


async def _build_search_block(
    db: AsyncSession,
    message: str,
    history: list[schemas.ChatMessage] | None = None,
) -> str:
    """Query products relevant to keywords in the user's message.

    Two-stage: prefer in-stock results with positive price; fall back to OOS
    matches so the AI can answer 'we have it but it's out of stock' truthfully.
    """
    keywords = _extract_search_keywords(message)
    keywords = _resolve_context_keywords(keywords, history or [])
    if not keywords:
        return ""

    # Store names and bare volumes live in search_term/volume, NOT in title/brand,
    # so they must not be matched against text. Keeping them here would also be
    # dead OR-terms. Strip them to get the real product/brand keywords.
    content_kw = [
        k for k in keywords
        if k not in _STORE_TOKENS and not _is_volume_only_keyword(k)
    ]
    search_kw = content_kw or keywords

    # OR across keywords for broad recall (AND would drop everything the moment
    # a stray non-stopword like "можешь" sneaks into the keyword list). We then
    # RANK in Python by how many keywords actually appear in title+brand, so
    # exact matches ("Versace Eros") rise to the top instead of being pushed out
    # of the LIMIT by alphabetical store order — which previously hid the notino
    # listing and made the assistant falsely claim "not available on Notino".
    conditions = [
        or_(Product.title.ilike(f"%{kw}%"), Product.brand.ilike(f"%{kw}%"))
        for kw in search_kw[:5]
    ]

    in_stock_stmt = (
        select(Product)
        .where(
            or_(*conditions),
            Product.is_available.is_(True),
            Product.last_price > 0,
            Product.last_seen >= datetime.utcnow() - timedelta(days=_FRESH_DAYS),
        )
        .order_by(Product.last_price)
        .limit(300)  # broad fetch; ranked + per-store capped in Python below
    )
    all_in_stock = (await db.execute(in_stock_stmt)).scalars().all()

    def _relevance(p: Product) -> int:
        hay = f"{p.brand or ''} {p.title or ''}".lower()
        return sum(1 for kw in search_kw if kw in hay)

    def _extra_words(p: Product) -> int:
        # "Eau Sauvage" or "Sauvage Elixir" are other fragrances than "Sauvage":
        # titles with fewer words beyond the query match it more exactly.
        brand = (p.brand or "").lower().split()
        words = re.findall(r"[^\W\d_]+", (p.title or "").lower())
        return sum(1 for w in words if w not in brand and w != "ml" and not any(w in kw or kw in w for kw in search_kw))

    # Most-relevant first so the per-store cap keeps the best matches (e.g. the
    # notino "Versace Eros" row beats an unrelated Versace product elsewhere);
    # then the closest names, cheapest first (the query is price-ordered and
    # sorted() is stable).
    all_in_stock = sorted(all_in_stock, key=lambda p: (-_relevance(p), _extra_words(p)))
    # "Dior Sauvage" should not bring in Creed Neroli Sauvage: when some rows
    # match two or more keywords, drop the rows that match fewer.
    best = _relevance(all_in_stock[0]) if all_in_stock else 0
    if best >= 2:
        all_in_stock = [p for p in all_in_stock if _relevance(p) == best]

    # Cap at 8 products per store so no single retailer dominates the context.
    _PER_STORE_LIMIT = 8
    store_counts: dict[str, int] = {}
    in_stock: list[Product] = []
    for p in all_in_stock:
        store = p.search_term or ""
        if store_counts.get(store, 0) < _PER_STORE_LIMIT:
            in_stock.append(p)
            store_counts[store] = store_counts.get(store, 0) + 1

    fallback_stmt = (
        select(Product)
        .where(
            or_(*conditions),
            or_(
                Product.is_available.is_(False),
                Product.last_price.is_(None),
                Product.last_price <= 0,
            ),
        )
        .order_by(Product.search_term, Product.title, desc(Product.last_seen))
        .limit(40)
    )
    all_oos = (await db.execute(fallback_stmt)).scalars().all()
    all_oos = sorted(all_oos, key=_relevance, reverse=True)

    # For OOS: cap at 3 per store to keep context tight.
    oos_store_counts: dict[str, int] = {}
    oos: list[Product] = []
    for p in all_oos:
        store = p.search_term or ""
        if oos_store_counts.get(store, 0) < 3:
            oos.append(p)
            oos_store_counts[store] = oos_store_counts.get(store, 0) + 1

    if not in_stock and not oos:
        return ""

    sections: list[str] = []
    if in_stock:
        stores_repr = ", ".join(sorted(store_counts.keys()))
        sections.append(_format_search_results(
            in_stock,
            f"IN-STOCK matches ({len(in_stock)}) across stores "
            f"[{stores_repr}] — authoritative live database data:",
        ))
    if oos:
        oos_stores = ", ".join(sorted(oos_store_counts.keys()))
        sections.append(_format_search_results(
            oos,
            f"Also matching but OUT OF STOCK ({len(oos)}) at "
            f"[{oos_stores}] — tracked but not currently buyable:",
        ))
    return "\n\n".join(sections)


_CHEAPEST_MARKERS = {
    "дешев", "дешёв", "бюджет", "дешевле", "недорог", "экономн",
    "cheap", "cheapest", "affordable", "budget", "lowest", "inexpensive",
    "lētāk", "lētākais", "lēts", "lētu",
}
_EXPENSIVE_MARKERS = {
    "дорог", "дорогой", "дороже", "дорогост", "premiu", "люкс", "luksus",
    "expensive", "priciest", "highest", "most expensive",
    "dārgāk", "dārgākais", "dārgs",
}


def _detect_price_intent(message: str) -> str | None:
    """Return 'cheapest', 'expensive', or None."""
    lower = message.lower()
    for m in _CHEAPEST_MARKERS:
        if m in lower:
            return "cheapest"
    for m in _EXPENSIVE_MARKERS:
        if m in lower:
            return "expensive"
    return None


async def _build_price_ranking_block(db: AsyncSession, intent: str) -> str:
    """Return top-5 in-stock products by price (asc/desc) across all stores."""
    order = Product.last_price if intent == "cheapest" else desc(Product.last_price)
    stmt = (
        select(Product)
        .where(
            Product.is_available.is_(True),
            Product.last_price > 0,
        )
        .order_by(order)
        .limit(10)
    )
    products = (await db.execute(stmt)).scalars().all()
    if not products:
        return ""

    label = "CHEAPEST in-stock products" if intent == "cheapest" else "MOST EXPENSIVE in-stock products"
    lines = [f"{label} across all tracked stores:"]
    # Cap at 3 per store so all stores get a chance to appear
    store_counts: dict[str, int] = {}
    shown = 0
    for p in products:
        store = p.search_term or ""
        if store_counts.get(store, 0) >= 3:
            continue
        store_counts[store] = store_counts.get(store, 0) + 1
        lines.append(
            f"• {p.brand or ''} {p.title} — "
            f"€{float(p.last_price):.2f} at {p.search_term}"
        )
        shown += 1
        if shown >= 5:
            break
    return "\n".join(lines)


async def _build_spreads_block(db: AsyncSession) -> str:
    # Find ProductGroups with the largest price gap across stores
    spread_stmt = (
        select(
            Product.group_id,
            func.min(Product.last_price).label("min_price"),
            func.max(Product.last_price).label("max_price"),
            func.count(Product.id).label("store_count"),
        )
        .where(
            Product.group_id.isnot(None),
            Product.last_price.isnot(None),
            Product.last_price > 0,
            Product.is_available.is_(True),
        )
        .group_by(Product.group_id)
        .having(func.count(Product.id) > 1)
        .order_by(
            desc(func.max(Product.last_price) - func.min(Product.last_price))
        )
        .limit(5)
    )
    rows = (await db.execute(spread_stmt)).all()
    if not rows:
        return "No significant cross-store spreads found."

    lines = []
    for row in rows:
        cheap_p = (
            await db.execute(
                select(Product)
                .where(
                    Product.group_id == row.group_id,
                    Product.last_price == row.min_price,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        exp_p = (
            await db.execute(
                select(Product)
                .where(
                    Product.group_id == row.group_id,
                    Product.last_price == row.max_price,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if cheap_p and exp_p:
            save_pct = (
                (float(row.max_price) - float(row.min_price))
                / float(row.min_price)
                * 100
            )
            lines.append(
                f"• {cheap_p.title}: cheapest €{float(row.min_price):.2f} "
                f"({cheap_p.search_term}) vs "
                f"€{float(row.max_price):.2f} ({exp_p.search_term}), "
                f"save {save_pct:.0f}%"
            )
    return "\n".join(lines) if lines else "No cross-store spreads found."


@router.post(
    "",
    response_model=schemas.ChatResponse,
    dependencies=[Depends(limit("chat", 20, 600))],
)
async def chat(
    payload: schemas.ChatRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI chat endpoint — injects live DB context into Gemini prompt."""
    try:
        favorites_block = await _build_favorites_block(db, user.id)
        drops_block = await _build_drops_block(db)
        spreads_block = await _build_spreads_block(db)
        search_block = await _build_search_block(db, payload.message, payload.history)
        price_intent = _detect_price_intent(payload.message)
        price_ranking_block = (
            await _build_price_ranking_block(db, price_intent)
            if price_intent and not search_block
            else ""
        )

        # Conversation history (last 6 messages for context)
        history_lines = [
            f"{'User' if m.role == 'user' else 'Assistant'}: {m.content}"
            for m in payload.history[-6:]
        ]
        history_block = "\n".join(history_lines)

        today = datetime.utcnow().strftime("%Y-%m-%d")
        # What the user is looking at (product page, catalogue filters), so
        # "is this a good price?" needs no restating. Plain text from the UI.
        page = (payload.page_context or "").strip()[:300]
        page_block = f"The user is currently viewing: {page}\n" if page else ""
        full_prompt = (
            f"You are MarketPulse AI — a price intelligence assistant for the "
            f"Latvian perfume market.\n"
            f"You track prices across 4 stores: Notino, Douglas, Makeup.lv, "
            f"220.lv.\n"
            f"Today's date: {today}\n"
            f"{page_block}\n"
            f"RULES — follow strictly:\n"
            f"1. Match the user's language (Latvian, English, or Russian).\n"
            f"2. Answer concisely. Do NOT proactively list all market data "
            f"unless the user specifically asks for it.\n"
            f"3. You are STRICTLY a price intelligence assistant. NEVER tell "
            f"jokes, poems, stories, or engage with any off-topic request — "
            f"even if framed around perfume. If asked for anything unrelated "
            f"to prices, availability, or product search, politely decline in "
            f"one sentence and ask what fragrance the user is looking for.\n"
            f"4. You are READ-ONLY. You CANNOT add/remove favorites, place "
            f"orders, or perform any actions. If asked to do so, explain that "
            f"you can only provide information and direct the user to use the "
            f"Favorites button on the product page in the UI.\n"
            f"5. The '=== PRODUCTS MATCHING YOUR QUERY ===' block (when "
            f"present) is the AUTHORITATIVE result of a live database search "
            f"for the user's query. NEVER invent product names, series, or "
            f"variants beyond what is listed there. NEVER claim a product is "
            f"missing if it appears in that block. If the block lists items "
            f"as OUT OF STOCK, say so honestly — but still acknowledge the "
            f"product IS tracked in the database.\n"
            f"6. If '=== PRODUCTS MATCHING YOUR QUERY ===' is absent or empty "
            f"for a product question, reply that the product is not currently "
            f"in our tracked database — do NOT guess.\n"
            f"7. Use other context blocks (watchlist, drops, spreads) ONLY "
            f"when directly relevant to the user's question.\n"
            f"8. When presenting product listings, group by fragrance line "
            f"(name), placing all sizes/volumes of the same product together "
            f"before moving to the next line. Within each line, list cheapest "
            f"first. For cross-store comparisons, group first by store.\n"
            f"8a. A different name is a different fragrance: 'Eau Sauvage', "
            f"'Sauvage Elixir' or 'Sauvage Eau Forte' are NOT 'Sauvage'. Only "
            f"answer with the exact line the user asked for unless they ask "
            f"for related lines. Always state the concentration (EDT, EDP, "
            f"Parfum) and volume, and compare prices only between the same "
            f"concentration and volume. When a promo price is listed, it is "
            f"the price to pay: show it (with the code, if any).\n"
            f"9. RESPONSE LENGTH LIMIT — strict:\n"
            f"   a) Show at most 5 products TOTAL per response, across all stores combined.\n"
            f"   b) If the query is broad (a brand name, a generic category) AND "
            f"the database block contains more than 5 results, do NOT list them all. "
            f"Instead: give a 1-2 sentence summary (how many found, price range, "
            f"which stores), then ask a follow-up question to narrow down, e.g.:\n"
            f"   → 'Hugo Boss есть в наличии в 3 магазинах (от €24 до €120). "
            f"Показать по конкретной серии? | Только самые дешёвые? | Сравнить по объёму?'\n"
            f"   c) For SPECIFIC product queries (exact name + volume), show matching "
            f"items directly (up to 5).\n"
            f"   d) Never end a response without a short follow-up chip line "
            f"(2-3 options, user's language). Format: → Option 1? | Option 2? | Option 3?\n"
            f"   A concise answer + follow-up question is ALWAYS better than a wall of text.\n"
            f"10. GENDER: Products in this database are NOT tagged by gender. "
            f"You have NO reliable information about whether a fragrance is "
            f"men's, women's, or unisex. NEVER claim the database contains "
            f"'thousands of women's fragrances' or make any gender-based "
            f"assertions. If asked about women's/men's fragrances, say you "
            f"cannot filter by gender and ask for a brand or product name "
            f"instead.\n"
            f"11. OOS QUERIES: If the user asks to 'show all out-of-stock "
            f"products' without naming a specific product, do NOT claim you "
            f"have no data — OOS products ARE tracked. Instead, explain that "
            f"the database tracks thousands of products and ask them to name "
            f"a specific fragrance to check its availability.\n\n"
            f"=== USER'S WATCHLIST ===\n{favorites_block}\n\n"
            f"=== RECENT PRICE DROPS (last 7 days) ===\n{drops_block}\n\n"
            f"=== BEST CROSS-STORE DEALS NOW ===\n{spreads_block}\n"
        )
        if search_block:
            full_prompt += (
                f"\n=== PRODUCTS MATCHING YOUR QUERY ===\n{search_block}\n"
            )
        if price_ranking_block:
            full_prompt += (
                f"\n=== PRICE RANKING (live DB) ===\n{price_ranking_block}\n"
            )
        if history_block:
            full_prompt += f"\n=== CONVERSATION HISTORY ===\n{history_block}\n"
        full_prompt += f"\nUser: {payload.message}"

        response = await ai_generator.client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=full_prompt,
        )
        return schemas.ChatResponse(reply=response.text.strip())

    except Exception as e:
        logger.error(f"[CHAT] Error processing request: {e}")
        return schemas.ChatResponse(
            reply="Sorry, I couldn't process your request. Please try again."
        )
