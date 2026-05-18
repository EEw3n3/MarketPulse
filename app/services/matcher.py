import re
from typing import Optional, Dict
from sqlmodel import select
from thefuzz import fuzz
from loguru import logger

from app.domain.models import ProductGroup, Product
from app.services.normalizer import perfume_normalizer

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

        # 2. Strict Matching Phase
        # Search for a group that has the SAME brand, volume, concentration and a similar name.
        # Note: We store the "Canonical Name" in ProductGroup.name
        
        # Build query for candidates
        stmt = select(ProductGroup).where(
            ProductGroup.category == "Perfume" # Optionally restrict by category
        )
        results = await session.execute(stmt)
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
