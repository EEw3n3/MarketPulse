import re
from typing import Optional, Dict
from sqlalchemy import or_
from sqlmodel import select
from thefuzz import fuzz
from loguru import logger

from app.domain.models import ProductGroup, Product
from app.services.normalizer import perfume_normalizer


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

    # Threshold for fuzzy name matching if strict attributes don't match 100%
    FUZZY_THRESHOLD = 90

    async def find_best_match(self, session, product_data: Dict) -> Optional[ProductGroup]:
        """
        Tries to find an existing ProductGroup (Chain) for the given perfume.
        Matches by Brand, Volume, Concentration and normalized name.

        PERFORMANCE: instead of fetching ALL ProductGroups and running fuzzy
        match against every one (O(N) where N grows unbounded), we pre-filter
        at the SQL level by brand prefix. ProductGroup.name is built as
        "<Brand> <Product> <Concentration>" by get_canonical_name(), so the
        brand always appears at the start. With ~3000+ groups and ~50 known
        brands, this turns each find_best_match() call from scanning 3000
        groups into scanning ~30-100. Net ~30x speedup on bulk re-uploads.

        Aliases (JPG ↔ Jean Paul Gaultier, MFK ↔ Maison Francis Kurkdjian,
        D&G ↔ Dolce & Gabbana, YSL ↔ Yves Saint Laurent, V&R ↔ Viktor & Rolf,
        Fitch ↔ Abercrombie & Fitch) are tried in both directions so an
        incoming "JPG" matches groups stored as "Jean Paul Gaultier ...".
        """
        # 1. Get raw product attributes
        title = product_data.get("title", "")
        explicit_brand = product_data.get("brand")
        norm = perfume_normalizer.extract_all(title, explicit_brand=explicit_brand)

        # Use explicit brand if normalizer didn't find one in the title
        brand = explicit_brand or norm["brand"]
        volume = norm.get("volume") or product_data.get("volume")
        concentration = norm.get("concentration") or product_data.get("concentration")
        clean_name = norm["clean_name"]

        if not brand or not clean_name:
            # DANGER ZONE: If we don't have a reliable brand and clean name,
            # do NOT cluster items. Fallback to strict full-title fuzzy match.
            return await self._fuzzy_fallback(session, title)

        # 2. Strict Matching Phase — pre-filter by brand prefix (with aliases).
        stmt = select(ProductGroup).where(ProductGroup.category == "Perfume")
        brand_variants = _brand_search_variants(brand)
        if brand_variants:
            prefix_clauses = [
                ProductGroup.name.ilike(f"{_sql_escape_like(v)}%", escape="\\")
                for v in brand_variants
            ]
            stmt = stmt.where(or_(*prefix_clauses))

        results = await session.execute(stmt)
        groups = results.scalars().all()

        # Safety net: if pre-filter accidentally returns nothing (e.g. brand
        # text differs from canonical form in some edge case), fall back to
        # the legacy full scan so we don't accidentally start a duplicate
        # group for an existing perfume.
        if not groups and brand_variants:
            results = await session.execute(select(ProductGroup).where(
                ProductGroup.category == "Perfume"
            ))
            groups = results.scalars().all()

        for group in groups:
            # Normalize the group's canonical name to extract its attributes.
            group_norm = perfume_normalizer.extract_all(group.name)

            # Rule 1: Brand must match 100% (if present)
            if brand and group_norm["brand"] and brand.lower() != group_norm["brand"].lower():
                continue

            # Rule 2: Concentration must match exactly (or both null).
            # "Chanel Bleu EDT" and "Chanel Bleu Parfum" are DIFFERENT perfumes
            # and must never share a chain. Lenient "one null is OK" mode was
            # rejected because it lets products with missing concentration
            # (Douglas catalog, ~6% of rows) silently attach to whichever EDT/
            # EDP group was created first, polluting cross-store comparisons.
            this_conc = (concentration or "").lower()
            grp_conc = (group_norm["concentration"] or "").lower()
            if this_conc != grp_conc:
                continue

            # Rule 3: Name Similarity (Fuzzy)
            if not clean_name or not group_norm["clean_name"]:
                continue

            score = fuzz.token_sort_ratio(clean_name.lower(), group_norm["clean_name"].lower())

            if score >= self.FUZZY_THRESHOLD:
                logger.info(
                    f"🔗 CHAIN LINKED! ({score}%, conc={concentration or '∅'}): "
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
        final_brand = brand or norm["brand"]
        final_concentration = concentration or norm["concentration"]

        parts: list[str] = []
        if final_brand:
            parts.append(final_brand)

        # clean_name may still contain brand tokens when the normalizer didn't
        # recognize the brand (i.e. brand not in BRANDS list, came from
        # explicit_brand). Strip them so the unique product designation survives.
        product_token = (norm["clean_name"] or "").strip()
        if product_token and final_brand:
            # Strip the brand phrase as a whole, then any leftover brand-word tokens.
            product_token = re.sub(
                rf'\b{re.escape(final_brand)}\b', '', product_token, flags=re.IGNORECASE
            )
            for bw in final_brand.split():
                if len(bw) > 2:
                    product_token = re.sub(
                        rf'\b{re.escape(bw)}\b', '', product_token, flags=re.IGNORECASE
                    )
            product_token = re.sub(r'\s+', ' ', product_token).strip(" -,.:|/")

        if product_token:
            parts.append(product_token)

        if final_concentration:
            parts.append(final_concentration)

        # Final cleanup: unique words in order
        final_parts = []
        seen = set()
        for p in " ".join(parts).split():
            low = p.lower().strip("-,.")
            if low not in seen and len(low) > 1:
                final_parts.append(p)
                seen.add(low)

        # If after all stripping nothing distinctive remains, fall back to the
        # full title (minus volume) — guarantees uniqueness per scraped row.
        if not final_parts or len(" ".join(final_parts)) < 3:
            clean_title = perfume_normalizer.REGEX_VOLUME.sub("", title).strip("-,. |/")
            generics = {"man", "men", "woman", "women", "pour", "for", "eau", "de", "set"}
            if clean_title.lower() in generics:
                return title
            return clean_title if len(clean_title) > 2 else title

        return " ".join(final_parts)

matcher_service = MatcherService()
