"""Public, read-only teaser for the landing page.

Only aggregate shop prices that anyone can see on the shops' own sites; no
user data. Cached in-process because the landing page is the busiest page.
"""
import time

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import schemas
from app.api.cards import cards_for_keys
from app.api.deps import get_db
from app.services import market

router = APIRouter(prefix="/public", tags=["public"])

_CACHE: dict = {"at": 0.0, "value": None}
_TTL = 900


def _distinct(cards: list[schemas.CatalogCard], n: int) -> list[schemas.CatalogCard]:
    """First `n` cards with different perfume names."""
    out, seen = [], set()
    for c in cards:
        name = (c.brand.lower(), c.name.lower())
        if name not in seen:
            seen.add(name)
            out.append(c)
    return out[:n]


@router.get("/landing", response_model=schemas.LandingData)
async def landing(db: AsyncSession = Depends(get_db)):
    now = time.monotonic()
    if _CACHE["value"] is not None and now - _CACHE["at"] < _TTL:
        return _CACHE["value"]

    snap = await market.snapshot(db)
    hero_key = await market.hero_key(db)
    shelf = await market.shelf_keys(db, limit=4)
    gaps = await market.top_gap_keys(db, limit=6, min_shops=2)
    cards = {c.key: c for c in await cards_for_keys(db, list(dict.fromkeys([k for k in [hero_key, *shelf, *gaps] if k])))}
    value = schemas.LandingData(
        market=snap,
        hero=cards.get(hero_key) if hero_key else None,
        shelf=_distinct([cards[k] for k in shelf if k in cards], 4),
        gaps=[cards[k] for k in gaps if k in cards],
        drops=await market.recent_drops(db, days=30, limit=6, matched_only=True, max_move=0.5, min_price=25),
    )
    _CACHE.update(at=now, value=value)
    return value
