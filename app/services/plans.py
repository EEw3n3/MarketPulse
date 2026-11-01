"""Pro: who has it, until when, and the log of every change.

Pro is active while user.plan == "pro" and user.pro_until (UTC) is empty or
in the future. Every Pro check on the server goes through has_pro(), so Pro
ends the moment its term does: analytics and exports answer 403 and the site
(which takes is_pro from the server) shows the Free screens.

An expired account is switched to "free" with an "expire" row in the log the
next time it is loaded (any request of that user) or the admin opens Users;
expire_due() does all of them at once. The site sends no e-mails: three days
before the end a banner says "Pro until 30.11" instead.

A paid subscription (pro_source "payment", once payments arrive) is never
cut short by an admin: an admin grant only moves its end later.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import PlanChange, User

RIGA = ZoneInfo("Europe/Riga")
MAX_DAYS = 3660


def pro_active(user: User, now: Optional[datetime] = None) -> bool:
    if (user.plan or "free") != "pro":
        return False
    return user.pro_until is None or user.pro_until > (now or datetime.utcnow())


def has_pro(user: User) -> bool:
    """Admins get every Pro feature."""
    return bool(user.is_admin or pro_active(user))


def end_of_day(d: date) -> datetime:
    """The last second of `d` in Riga, as naive UTC (how the database stores time)."""
    local = datetime.combine(d, time(23, 59, 59), tzinfo=RIGA)
    return local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def _log(db: AsyncSession, user: User, action: str, by: Optional[User], note: Optional[str]) -> PlanChange:
    row = PlanChange(user_id=user.id, at=datetime.utcnow(), by_user_id=by.id if by else None, action=action,
                     plan=user.plan, pro_until=user.pro_until, source=user.pro_source,
                     note=(note or "").strip()[:255] or None)
    db.add(row)
    return row


def expire_if_due(db: AsyncSession, user: User, now: Optional[datetime] = None) -> bool:
    """Switch `user` to free when the term has passed. The caller commits."""
    now = now or datetime.utcnow()
    if (user.plan or "free") == "pro" and user.pro_until is not None and user.pro_until <= now:
        user.plan = "free"
        db.add(user)
        _log(db, user, "expire", None, None)
        return True
    return False


async def expire_due(db: AsyncSession) -> int:
    """Switch every expired account to free (commits)."""
    now = datetime.utcnow()
    users = (await db.execute(
        select(User).where(User.plan == "pro", User.pro_until.is_not(None), User.pro_until <= now)
    )).scalars().all()
    for u in users:
        expire_if_due(db, u, now)
    if users:
        await db.commit()
    return len(users)


def grant(db: AsyncSession, user: User, by: Optional[User], *, days: Optional[int] = None,
          until: Optional[date] = None, forever: bool = False, note: Optional[str] = None) -> User:
    """Give Pro: for `days` (counted from the current end while Pro is
    active), until the end of the day `until` (Riga), or without an end.
    The caller commits."""
    now = datetime.utcnow()
    active = pro_active(user, now)
    if forever:
        new_until: Optional[datetime] = None
    elif days is not None:
        if not 1 <= days <= MAX_DAYS:
            raise ValueError(f"days must be 1..{MAX_DAYS}")
        # Counted from the current end; Pro without an end gets a term from today.
        base = user.pro_until if active and user.pro_until is not None else now
        new_until = base + timedelta(days=days)
    elif until is not None:
        new_until = end_of_day(until)
        if new_until <= now:
            raise ValueError("the date is in the past")
    else:
        raise ValueError("give days, a date or forever")

    paid = active and user.pro_source == "payment"
    if paid and user.pro_until is not None and new_until is not None and new_until < user.pro_until:
        new_until = user.pro_until  # never shorten a paid term
    action = "extend" if active else "grant"
    user.plan = "pro"
    user.pro_until = new_until
    user.pro_source = "payment" if paid else "admin"
    db.add(user)
    _log(db, user, action, by, note)
    return user


def revoke(db: AsyncSession, user: User, by: Optional[User], note: Optional[str] = None) -> User:
    """Take Pro away now. The caller commits."""
    user.plan = "free"
    user.pro_until = None
    user.pro_source = None
    db.add(user)
    _log(db, user, "revoke", by, note)
    return user


async def history(db: AsyncSession, user_id: int, limit: int = 50) -> list[PlanChange]:
    return list((await db.execute(
        select(PlanChange).where(PlanChange.user_id == user_id).order_by(PlanChange.at.desc()).limit(limit)
    )).scalars().all())
