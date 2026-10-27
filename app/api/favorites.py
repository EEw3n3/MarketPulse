"""Favorites (watchlist) endpoints — protected, per-user.

All routes require a valid JWT. Favorites are scoped to the authenticated user;
no route returns or mutates another user's rows.
"""
from collections import defaultdict
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError

from app.api import schemas
from app.api.deps import get_current_user, get_db
from app.domain.models import Favorite, Product, User
from app.services.price_series import (
    by_store,
    change_percent,
    cheapest_line,
    cheapest_shop_by_day,
    day_range,
    display_name,
    product_series,
    store_key,
    store_label,
)

router = APIRouter(prefix="/favorites", tags=["favorites"])


def _delta(last_price, old_price) -> tuple[float, str]:
    """Rounded percent + direction, as float (frontend wants decimals)."""
    if not old_price or float(old_price) == 0:
        return 0.0, "none"
    diff = float(last_price) - float(old_price)
    if abs(diff) < 0.01:
        return 0.0, "none"
    percent = round(abs(diff) / float(old_price) * 100, 1)
    return percent, "up" if diff > 0 else "down"


def _favorite_to_item(fav: Favorite, product: Product) -> schemas.FavoriteItem:
    percent, direction = _delta(product.last_price, product.old_price)
    return schemas.FavoriteItem(
        id=fav.id,
        product_id=product.id,
        brand=product.brand,
        title=product.title,
        volume=product.volume,
        concentration=product.concentration,
        image_url=product.image_url,
        current_price=float(product.last_price or 0),
        previous_price=float(product.old_price) if product.old_price else None,
        price_when_added=float(fav.price_when_added) if fav.price_when_added else None,
        change_percent=percent,
        change_direction=direction,
        store_name=(product.search_term or "unknown").capitalize(),
        is_available=product.is_available,
        alert_enabled=fav.alert_enabled,
        alert_threshold_percent=float(fav.alert_threshold_percent) if fav.alert_threshold_percent is not None else None,
        created_at=fav.created_at,
    )


def _vol(v: Optional[str]) -> str:
    return (v or "").lower().replace(" ", "")


async def _with_market(db: AsyncSession, items: list[tuple[Favorite, Product]]) -> list[schemas.FavoriteItem]:
    """Favorites plus the same bottle in every shop and 30 days of prices."""
    group_ids = {p.group_id for _, p in items if p.group_id}
    siblings: dict[tuple[int, str], list[Product]] = defaultdict(list)
    if group_ids:
        rows = (await db.execute(
            select(Product).where(Product.group_id.in_(group_ids), Product.last_price > 0)
        )).scalars().all()
        for p in rows:
            siblings[(p.group_id, _vol(p.volume))].append(p)

    bottles: dict[int, list[Product]] = {}
    for fav, product in items:
        same = siblings.get((product.group_id, _vol(product.volume)), []) if product.group_id else []
        if product not in same:
            same = [*same, product]
        bottles[fav.id] = same

    days = day_range(30)
    every = {p.id: p for same in bottles.values() for p in same}
    per_product = await product_series(db, every.values(), days)

    out = []
    for fav, product in items:
        item = _favorite_to_item(fav, product)
        same = bottles[fav.id]
        cheapest: dict[str, Product] = {}
        for p in sorted(same, key=lambda p: (not p.is_available, float(p.last_price or 0))):
            cheapest.setdefault(store_key(p.search_term), p)
        item.offers = [
            schemas.FavoriteOffer(
                product_id=p.id,
                store=key,
                store_name=store_label(key),
                price=float(p.last_price),
                old_price=float(p.old_price) if p.old_price else None,
                url=p.url,
                is_available=p.is_available,
            )
            for key, p in sorted(cheapest.items(), key=lambda kv: (not kv[1].is_available, float(kv[1].last_price)))
        ]
        lines = by_store(same, per_product)
        item.series = schemas.PriceSeries(
            days=[d.isoformat() for d in days], shops=lines, cheapest=cheapest_shop_by_day(lines)
        )
        item.change_30d = change_percent(cheapest_line(lines), 30)
        item.display_name = display_name(same)
        out.append(item)
    return out


@router.get("", response_model=list[schemas.FavoriteItem])
async def list_favorites(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """All favorites for the current user, newest first. Joins product data."""
    stmt = (
        select(Favorite, Product)
        .join(Product, Product.id == Favorite.product_id)
        .where(Favorite.user_id == user.id)
        .order_by(Favorite.created_at.desc())
    )
    result = await db.execute(stmt)
    return await _with_market(db, [(fav, prod) for fav, prod in result.all()])


@router.post("", response_model=schemas.FavoriteItem, status_code=status.HTTP_201_CREATED)
async def add_favorite(
    payload: schemas.FavoriteCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pin a product. 404 if product missing, 409 if already favorited."""
    product = await db.get(Product, payload.product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    fav = Favorite(
        user_id=user.id,
        product_id=product.id,
        alert_enabled=payload.alert_enabled,
        price_when_added=product.last_price,
    )
    db.add(fav)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product already in favorites",
        )
    await db.refresh(fav)
    return _favorite_to_item(fav, product)


@router.patch("/{product_id}", response_model=schemas.FavoriteItem)
async def update_favorite(
    product_id: int,
    payload: schemas.FavoriteUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle alert_enabled or set the personal drop threshold of a favorite.
    Keyed by product_id (frontend-friendly). A threshold of 0 clears it."""
    stmt = (
        select(Favorite, Product)
        .join(Product, Product.id == Favorite.product_id)
        .where(Favorite.user_id == user.id, Favorite.product_id == product_id)
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Favorite not found")

    fav, product = row
    if payload.alert_enabled is not None:
        fav.alert_enabled = payload.alert_enabled
    if payload.alert_threshold_percent is not None:
        fav.alert_threshold_percent = (
            Decimal(str(payload.alert_threshold_percent)) if payload.alert_threshold_percent > 0 else None
        )
    await db.commit()
    await db.refresh(fav)
    return _favorite_to_item(fav, product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_favorite(
    product_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a favorite by product_id. 404 if it doesn't exist."""
    stmt = select(Favorite).where(
        Favorite.user_id == user.id,
        Favorite.product_id == product_id,
    )
    fav = (await db.execute(stmt)).scalar_one_or_none()
    if not fav:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Favorite not found")

    await db.delete(fav)
    await db.commit()
    return None
