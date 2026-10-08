import re
from typing import Optional, Dict
from sqlalchemy import or_
from sqlmodel import select
from thefuzz import fuzz
from loguru import logger

from app.domain.models import ProductGroup, Product
from app.services.normalizer import (
    perfume_normalizer, brand_key, name_key, names_match, strip_leading_brand,
)


def _brand_search_variants(brand: str) -> list[str]:
    """For a brand string, return every form that could appear at the start
    of a ProductGroup.name. Handles BRAND_ALIASES in both directions so an
    incoming product with brand="JPG" finds groups named "Jean Paul Gaultier ..."
    AND an incoming "Jean Paul Gaultier" finds legacy groups under "JPG ...".
    """
    if not brand:
        return []
    seen = set()
    variants: list[str] = []
    def _add(b: str) -> None:
        b = b.strip()
        if not b or b.lower() in seen:
            return
        seen.add(b.lower())
        variants.append(b)
    _add(brand)
    aliases = perfume_normalizer.BRAND_ALIASES
    # Forward: short alias → long canonical (e.g. JPG → Jean Paul Gaultier)
    if brand in aliases:
        _add(aliases[brand])
    # Reverse: long canonical → known short aliases
    for short, long_form in aliases.items():
        if long_form.lower() == brand.lower():
            _add(short)
    return variants


def _sql_escape_like(s: str) -> str:
    """Escape ILIKE wildcards (% _ \\) so brand text with these chars works
    as a literal prefix."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class MatcherService:
    """
    The Brain of the operation.
    Links products across different sites into unified 'Chains' (ProductGroups).
    """

    def __init__(self) -> None:
        # Parsed group names, (group name, brand key) → (concentration, name key).
        # Group names only change in a regroup, which runs in its own process.
        self._group_cache: dict[tuple[str, str], Optional[tuple[str, dict]]] = {}

    def parse_group_name(self, group_name: str, brand: str) -> Optional[tuple[str, dict]]:
        """(concentration, name_key) of a group name built by get_canonical_name,
        or None when the name does not start with this brand."""
        cache_key = (group_name, brand_key(brand))
        if cache_key not in self._group_cache:
            parsed = None
            rest = strip_leading_brand(group_name, {cache_key[1]})
            if rest != group_name.lstrip(" -–—,.|/:"):
                norm = perfume_normalizer.extract_all(group_name, explicit_brand=brand)
                parsed = ((norm["concentration"] or "").lower(), name_key(norm["clean_name"], brand))
            self._group_cache[cache_key] = parsed
        return self._group_cache[cache_key]

    async def find_best_match(self, session, product_data: Dict) -> Optional[ProductGroup]:
        """
        Tries to find an existing ProductGroup (Chain) for the given perfume.

        A group matches when its name starts with the same brand (any spelling
        or alias: "HERMÈS" = "Hermes", "ARMANI" = "Giorgio Armani"), has the
        same concentration and the same name (names_match: every word has its
        twin, so "Molecule 01" ≠ "Molecule 02"). Volume is not part of a group.

        PERFORMANCE: groups are pre-filtered in SQL by brand prefix
        (ProductGroup.name is "<Brand> <Product> <Concentration>", see
        get_canonical_name), so each call looks at the brand's groups only.
        """
        title = product_data.get("title", "")
        norm = perfume_normalizer.extract_all(title, explicit_brand=product_data.get("brand"))
        brand = norm["brand"]
        concentration = (norm.get("concentration") or product_data.get("concentration") or "").lower()

        if not brand:
            # No brand: fall back to a strict full-title fuzzy match.
            return await self._fuzzy_fallback(session, title)
        key = name_key(norm["clean_name"], brand)

        # Strict Matching Phase — pre-filter by brand prefix (with aliases).
        stmt = select(ProductGroup).where(ProductGroup.category == "Perfume")
        brand_variants = _brand_search_variants(brand)
        # ...and every other spelling of the brand (raw shop form, BRANDS entries
        # with the same key: "Armani" for "Giorgio Armani").
        same_brand = [b for b in perfume_normalizer.BRANDS if brand_key(b) == brand_key(brand)]
        for raw in [product_data.get("brand"), *same_brand]:
            for v in _brand_search_variants(raw or ""):
                if v.lower() not in {b.lower() for b in brand_variants}:
                    brand_variants.append(v)
        prefix_clauses = [
            ProductGroup.name.ilike(f"{_sql_escape_like(v)}%", escape="\\")
            for v in brand_variants
        ]
        groups = (await session.execute(stmt.where(or_(*prefix_clauses)))).scalars().all()

        for group in groups:
            parsed = self.parse_group_name(group.name, brand)
            if parsed is None:
                continue
            group_conc, group_key = parsed
            # Concentration must match exactly (or both null). "Chanel Bleu EDT"
            # and "Chanel Bleu Parfum" are different perfumes; a product without
            # a concentration must not attach to whichever EDT/EDP group came first.
            if concentration != group_conc:
                continue
            if names_match(key, group_key):
                logger.info(
                    f"🔗 CHAIN LINKED! (conc={concentration or '∅'}): "
                    f"'{title}' joined '{group.name}'"
                )
                return group

        return None

    async def _fuzzy_fallback(self, session, title: str) -> Optional[ProductGroup]:
        """Strict fuzzy matching as a last resort."""
        stmt = select(ProductGroup)
        results = await session.execute(stmt)
        groups = results.scalars().all()
        
        for group in groups:
            score = fuzz.token_set_ratio(title.lower(), group.name.lower())
            if score >= 95: # Very strict
                return group
        return None

    def get_canonical_name(
        self,
        title: str,
        brand: Optional[str] = None,
        concentration: Optional[str] = None,
    ) -> str:
        """Returns a clean, standardized name for the ProductGroup.

        Must produce UNIQUE names per distinct product. Two different perfumes
        of the same brand+concentration must NEVER share a canonical name —
        otherwise `ON CONFLICT DO NOTHING` on ProductGroup.name silently merges
        them into one group, bypassing matcher fuzzy logic.

        `concentration` is an explicit override used when the scraper extracted
        it from structured product data (Tealium / page metadata) but the title
        string itself doesn't contain an EDT/EDP/Parfum keyword. Without this,
        e.g. all Makeup "Chanel Bleu 50ml" variants (whose `concentration`
        column is correctly populated but title is bare) collapse into one
        group because `extract_all(title)` returns None for concentration.
        """
        norm = perfume_normalizer.extract_all(title, explicit_brand=brand)
        final_brand = norm["brand"]
        final_concentration = concentration or norm["concentration"]
        product_token = norm["clean_name"] or ""

        parts = [p for p in (final_brand, product_token) if p]
        # "MYSLF Le Parfum" + Parfum: the label is already the last word.
        last_word = product_token.split()[-1].lower() if product_token else ""
        if final_concentration and final_concentration.lower() != last_word:
            parts.append(final_concentration)
        name = re.sub(r"\s+", " ", " ".join(parts)).strip()

        # If nothing distinctive remains, fall back to the full title (minus
        # volume) so the row still gets a group of its own.
        if len(name) < 3:
            clean_title = perfume_normalizer.REGEX_VOLUME.sub("", title).strip("-,. |/")
            return clean_title if len(clean_title) > 2 else title
        return name

matcher_service = MatcherService()
