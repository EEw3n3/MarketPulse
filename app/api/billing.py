"""Pro by card through Paddle (app/services/billing.py).

GET  /billing/config   checkout settings for the signed-in user
GET  /billing/me       the user's subscription: plan, renews or ends when
POST /billing/portal   a link to Paddle's customer portal (card, receipts, cancel)
POST /billing/webhook  Paddle's signed notifications (public, checked by signature)
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.rate_limit import limit
from app.domain.models import Subscription, User
from app.services import billing

router = APIRouter(prefix="/billing", tags=["billing"])


class PlanOut(BaseModel):
    term: Literal["month", "half", "year"]
    months: int
    amount: float
    price_id: Optional[str] = None


class BillingConfig(BaseModel):
    checkout: bool                     # this user may open the checkout now
    environment: Literal["sandbox", "production"]
    client_token: Optional[str] = None
    plans: list[PlanOut]


class SubscriptionOut(BaseModel):
    status: str
    term: Optional[str] = None
    current_period_end: Optional[datetime] = None
    cancel_at: Optional[datetime] = None
    manageable: bool = False           # a portal link can be made


@router.get("/config", response_model=BillingConfig)
async def config(user: User = Depends(get_current_user)):
    open_ = billing.checkout_open_to(user)
    return BillingConfig(
        checkout=open_,
        environment="sandbox" if billing.sandbox() else "production",
        client_token=settings.PADDLE_CLIENT_TOKEN if open_ else None,
        plans=[PlanOut(term=p.term, months=p.months, amount=p.amount,
                       price_id=billing.price_id(p) if open_ else None) for p in billing.PLANS],
    )


@router.get("/me", response_model=Optional[SubscriptionOut])
async def my_subscription(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    sub = (await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
        .order_by(Subscription.updated_at.desc()).limit(1)
    )).scalar_one_or_none()
    if sub is None:
        return None
    return SubscriptionOut(status=sub.status, term=sub.term, current_period_end=sub.current_period_end,
                           cancel_at=sub.cancel_at,
                           manageable=bool(sub.paddle_customer_id and settings.PADDLE_API_KEY))


@router.post("/portal", dependencies=[Depends(limit("billing-portal", 10, 300))])
async def portal(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    sub = (await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
        .order_by(Subscription.updated_at.desc()).limit(1)
    )).scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="No subscription")
    try:
        return {"url": await billing.portal_url(sub)}
    except billing.PaddleError as e:
        logger.warning(f"paddle portal for user {user.id}: {e}")
        raise HTTPException(status_code=502, detail="Paddle did not answer. Try again in a minute.")


@router.post("/webhook")
async def webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Paddle retries until it gets a 2xx: a bad signature is refused (401),
    a failure while applying answers 500 so the event comes again."""
    raw = await request.body()
    if not billing.verify_signature(raw, request.headers.get("paddle-signature")):
        logger.warning("paddle webhook: bad or missing signature")
        raise HTTPException(status_code=401, detail="Bad signature")
    try:
        event = json.loads(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="Not JSON")
    result = await billing.apply_event(db, event)
    await db.commit()
    logger.info(f"paddle {event.get('event_type')} {event.get('event_id')}: {result}")
    return {"ok": True}
