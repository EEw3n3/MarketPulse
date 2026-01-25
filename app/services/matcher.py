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
        norm = perfume_normalizer.extract_all(title)
        
        brand = norm["brand"]
        volume = norm["volume"]
        concentration = norm["concentration"]
        clean_name = norm["clean_name"]

        if not brand or not clean_name:
            # If we can't identify the brand or name, it's risky to link.
            # Fallback to a very strict fuzzy search on title.
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
            # For each group, we check if it matches our criteria
            # We might want to store attributes in ProductGroup eventually, 
            # but for now we can infer them from the group name or associated products.
            # Actually, a better way: check the products already in this group.
            
            # Since ProductGroup name is usually the first product's name,
            # let's normalize the Group Name too.
            group_norm = perfume_normalizer.extract_all(group.name)
            
            # Rule 1: Brand must match 100% (if present)
            if brand and group_norm["brand"] and brand.lower() != group_norm["brand"].lower():
                continue
            
            # Rule 2: Volume must match 100% (critical for chains!)
            if volume and group_norm["volume"] and volume != group_norm["volume"]:
                continue
                
            # Rule 3: Concentration must match 100%
            if concentration and group_norm["concentration"] and concentration != group_norm["concentration"]:
                continue

            # Rule 4: Name Similarity (Fuzzy)
            score = fuzz.token_sort_ratio(clean_name.lower(), group_norm["clean_name"].lower())
            
            if score >= self.FUZZY_THRESHOLD:
                logger.info(f"🔗 CHAIN LINKED! ({score}%): '{title}' joined '{group.name}'")
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

    def get_canonical_name(self, title: str) -> str:
        """Returns a clean, standardized name for the ProductGroup."""
        norm = perfume_normalizer.extract_all(title)
        parts = []
        if norm["brand"]: parts.append(norm["brand"])
        if norm["clean_name"]: parts.append(norm["clean_name"])
        if norm["concentration"]: parts.append(norm["concentration"])
        if norm["volume"]: parts.append(norm["volume"])
        
        if not parts: return title
        return " ".join(parts)

matcher_service = MatcherService()
