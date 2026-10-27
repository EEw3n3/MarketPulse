"""Catalogue filter clauses shared by the catalog, cards and export endpoints."""
from typing import List, Optional

from sqlalchemy import and_, func, or_

from app.domain.models import Product


def _store_filter_clause(stores: List[str]):
    """Case-insensitive substring match for stores. Frontend sends canonical keys
    ("notino", "douglas", "220", "makeup", "1a") — DB has mixed forms like
    "Notino", "notino.lv", "Douglas Latvia", "Makeup latvija", "1A.LV". A LOWER()
    LIKE %key% matches all variants reliably."""
    return or_(*(func.lower(Product.search_term).like(f"%{s.lower()}%") for s in stores))


def _expand_search_term_with_aliases(search: str) -> list[str]:
    """For a catalog search query, return the query plus every brand-alias
    equivalent so 'JPG' matches Jean Paul Gaultier products, 'YSL' matches
    Yves Saint Laurent, 'D&G' matches Dolce & Gabbana, etc.

    Without this, the search box appears broken for users who use industry
    shorthand brand names ("jpg le male") — perfume titles get stored in the
    long canonical form by the normalizer, so a literal LIKE '%jpg%' against
    titles/brands finds nothing.

    Match is case-insensitive and EITHER the full search query OR any token
    in it can match an alias key/value.
    """
    from app.services.normalizer import perfume_normalizer

    if not search:
        return []
    out: list[str] = [search]
    seen = {search.lower()}
    aliases = perfume_normalizer.BRAND_ALIASES
    search_lower = search.lower().strip()
    # Tokens in the search query — handles "jpg le male" (token 'jpg' matches alias)
    tokens = [t for t in search_lower.split() if t]
    candidates = {search_lower, *tokens}
    for cand in candidates:
        for short, long_form in aliases.items():
            if cand == short.lower():
                # Add the long canonical form too
                if long_form.lower() not in seen:
                    out.append(long_form)
                    seen.add(long_form.lower())
            elif cand == long_form.lower():
                # Add the short alias too
                if short.lower() not in seen:
                    out.append(short)
                    seen.add(short.lower())
    return out


def _brand_filter_clause(brands: List[str]):
    """Case-insensitive + alias-aware brand match for catalog/feed filters.

    The brand chips on the frontend send a canonical display name ("Dior",
    "YSL", "Dolce & Gabbana"), but `Product.brand` is stored inconsistently
    across stores:
      - Douglas: "DIOR" (uppercase)
      - Notino/Makeup/1a/220: "Dior"
      - 220.lv even has "Christian Dior"
      - "YSL" chip vs DB "Yves Saint Laurent"
    A plain `Product.brand.in_(brands)` is exact + case-sensitive, so e.g.
    filtering Douglas by "Dior" returned zero rows. We expand each requested
    brand through the same alias map used by search, lowercase everything,
    and substring-match — which also catches "Christian Dior" via "%dior%".
    """
    variants: set[str] = set()
    for b in brands:
        variants.add(b.lower())
        for v in _expand_search_term_with_aliases(b):
            variants.add(v.lower())
    return or_(*(func.lower(Product.brand).like(f"%{v}%") for v in variants))


def _concentration_clause(types: List[str]):
    """Concentration chips: EDP/EDT/Parfum/EDC plus "other" for blank values.

    Case-insensitive so the UI labels line up with however the value is cased
    in the DB.
    """
    wanted = [t.lower() for t in types]
    clauses = []
    named = [t for t in wanted if t != "other"]
    if named:
        clauses.append(func.lower(Product.concentration).in_(named))
    if "other" in wanted:
        clauses.append(or_(Product.concentration.is_(None), Product.concentration == ""))
    return or_(*clauses)


def apply_product_filters(
    stmt,
    search: Optional[str] = None,
    brands: Optional[List[str]] = None,
    stores: Optional[List[str]] = None,
    volumes: Optional[List[str]] = None,
    types: Optional[List[str]] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    in_stock: Optional[bool] = None,
    promo: Optional[bool] = None,
    ids: Optional[List[int]] = None,
):
    """Add the catalogue's filter clauses to a select over Product."""
    if search:
        # Expand short brand aliases (JPG → Jean Paul Gaultier, etc.) so the
        # search box works for industry-standard short names.
        search_variants = _expand_search_term_with_aliases(search)
        ors = []
        for s in search_variants:
            ors.append(Product.title.ilike(f"%{s}%"))
            ors.append(Product.brand.ilike(f"%{s}%"))
        # Word order should not matter: "bleu chanel edp" finds
        # "Chanel Bleu de Chanel" with concentration EDP.
        tokens = [t for t in search.split() if t]
        if len(tokens) > 1:
            ors.append(and_(*(
                or_(
                    Product.title.ilike(f"%{t}%"),
                    Product.brand.ilike(f"%{t}%"),
                    Product.concentration.ilike(t),
                )
                for t in tokens
            )))
        stmt = stmt.where(or_(*ors))
    if brands:
        stmt = stmt.where(_brand_filter_clause(brands))
    if stores:
        stmt = stmt.where(_store_filter_clause(stores))
    if volumes:
        stmt = stmt.where(Product.volume.in_(volumes))
    if types:
        stmt = stmt.where(_concentration_clause(types))
    if price_min is not None:
        stmt = stmt.where(Product.last_price >= price_min)
    if price_max is not None:
        stmt = stmt.where(Product.last_price <= price_max)
    if in_stock is not None:
        stmt = stmt.where(Product.is_available.is_(in_stock))
    if promo:
        stmt = stmt.where(Product.promo_price.isnot(None), Product.promo_price > 0)
    if ids:
        stmt = stmt.where(Product.id.in_(ids))
    return stmt
