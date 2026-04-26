"""Auth endpoints: register, login, me, preferences.

Public: POST /auth/register, POST /auth/login
Protected: GET /auth/me, PATCH /auth/preferences
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api import schemas
from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.domain.models import User, UserPreferences

router = APIRouter(prefix="/auth", tags=["auth"])


async def _load_preferences(db: AsyncSession, user_id: int) -> UserPreferences | None:
    res = await db.execute(select(UserPreferences).where(UserPreferences.user_id == user_id))
    return res.scalar_one_or_none()


def _build_user_read(user: User, prefs: UserPreferences | None) -> schemas.UserRead:
    return schemas.UserRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
        preferences=schemas.UserPreferencesRead.model_validate(prefs) if prefs else None,
    )


@router.post("/register", response_model=schemas.TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    """Create user + empty preferences in one transaction. Auto-promotes to admin if email == ADMIN_EMAIL."""
    email = payload.email.lower().strip()

    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    is_admin = bool(
        settings.ADMIN_EMAIL and email == settings.ADMIN_EMAIL.lower().strip()
    )

    user = User(
        email=email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        is_admin=is_admin,
    )
    db.add(user)
    await db.flush()  # assign user.id

    prefs = UserPreferences(user_id=user.id)
    db.add(prefs)
    await db.commit()
    await db.refresh(user)
    await db.refresh(prefs)

    token = create_access_token(subject=user.id)
    return schemas.TokenResponse(
        access_token=token,
        user=_build_user_read(user, prefs),
    )


@router.post("/login", response_model=schemas.TokenResponse)
async def login(payload: schemas.LoginRequest, db: AsyncSession = Depends(get_db)):
    email = payload.email.lower().strip()
    res = await db.execute(select(User).where(User.email == email))
    user = res.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account disabled",
        )

    prefs = await _load_preferences(db, user.id)
    token = create_access_token(subject=user.id)
    return schemas.TokenResponse(
        access_token=token,
        user=_build_user_read(user, prefs),
    )


@router.get("/me", response_model=schemas.UserRead)
async def me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prefs = await _load_preferences(db, user.id)
    return _build_user_read(user, prefs)


@router.patch("/preferences", response_model=schemas.UserPreferencesRead)
async def update_preferences(
    payload: schemas.UserPreferencesUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prefs = await _load_preferences(db, user.id)
    if not prefs:
        # Safety net — register() creates prefs, but handle legacy users or bad state.
        prefs = UserPreferences(user_id=user.id)
        db.add(prefs)

    if payload.monitored_stores is not None:
        prefs.monitored_stores = payload.monitored_stores
    if payload.interested_brands is not None:
        prefs.interested_brands = payload.interested_brands
    if payload.onboarding_completed is not None:
        prefs.onboarding_completed = payload.onboarding_completed

    await db.commit()
    await db.refresh(prefs)
    return schemas.UserPreferencesRead.model_validate(prefs)
