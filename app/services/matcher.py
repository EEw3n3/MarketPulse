from typing import Optional, List
from sqlmodel import select
from thefuzz import fuzz
from loguru import logger

from app.domain.models import ProductGroup, Product
from app.services.normalizer import volume_normalizer

class MatcherService:
    """
    The Brain of the operation.
    Decides if "Dior Sauvage EDT 100ml" is the same as "Sauvage Dior Eau De Toilette 0.1l".
    """
    
    # Threshold: Above this score, we consider it a match.
    # 85 is conservative. 90 is strict.
    MATCH_THRESHOLD = 85

    def _clean_title(self, title: str) -> str:
        """
        Removes noise to help TheFuzz focus on what matters.
        """
        if not title: return ""
        
        # 1. Normalize Volume (critical!)
        normalized = volume_normalizer.normalize_title(title)
        
        # 2. Lowercase
        text = normalized.lower()
        
        # 3. Remove fluff words that confuse matching
        garbage = [
            "eau de toilette", "eau de parfum", "edt", "edp", 
            "vīriešiem", "sievietēm", "for men", "for women",
            "spray", "dāvanu komplekts", "set", "tester",
            "only", "online", "new", "original"
        ]
        
        for g in garbage:
            text = text.replace(g, "")
            
        # 4. Remove extra spaces
        return " ".join(text.split())

    async def find_best_match(self, session, product_title: str) -> Optional[ProductGroup]:
        """
        Scans existing ProductGroups and tries to find a match.
        Returns the Group if found, else None.
        """
        clean_input = self._clean_title(product_title)
        
        # Performance optimization:
        # Instead of loading ALL groups, we could filter by first word?
        # For now, let's load all recent groups (assuming database isn't huge yet)
        # TODO: Optimize this when we have >10k groups.
        stmt = select(ProductGroup)
        results = await session.execute(stmt)
        groups = results.scalars().all()
        
        best_score = 0
        best_group = None
        
        for group in groups:
            # We match against the Group Name (which should be the "Canonical" name)
            clean_group_name = self._clean_title(group.name)
            
            # Token Set Ratio is good for "out of order" words but dangerous for subsets
            # "Versace Eros" vs "Versace" -> Set Ratio 100 (BAD)
            # "Versace Eros" vs "Versace" -> Sort Ratio 74 (GOOD DISTINCTION)
            
            set_score = fuzz.token_set_ratio(clean_input, clean_group_name)
            sort_score = fuzz.token_sort_ratio(clean_input, clean_group_name)
            
            # Weighted average: We value exact content (sort) more than partial (set)
            # to prevent "Brand Name" groups from swallowing everything.
            score = (set_score * 0.4) + (sort_score * 0.6)
            
            if score > best_score:
                best_score = score
                best_group = group
        
        if best_score >= self.MATCH_THRESHOLD:
            logger.info(f"🔗 MATCH FOUND! ({best_score}%): '{product_title}' -> '{best_group.name}'")
            return best_group
        
        logger.debug(f"🤷 No match for '{product_title}' (Best: {best_score}% with '{best_group.name if best_group else 'None'}')")
        return None

matcher_service = MatcherService()
