"""Auth endpoints: register, login, me, preferences.

Public: POST /auth/register, POST /auth/login
Protected: GET /auth/me, PATCH /auth/preferences
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api import schemas
from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.rate_limit import limit
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.domain.models import PlanChange, User, UserPreferences
from app.services.google_auth import GoogleTokenError, verify_id_token
from app.services.plans import has_pro, pro_active

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
        plan=user.plan,
        is_pro=has_pro(user),
        pro_until=user.pro_until if pro_active(user) else None,
        pro_source=user.pro_source if pro_active(user) else None,
        has_password=bool(user.hashed_password),
        google=bool(user.google_sub),
        created_at=user.created_at,
        preferences=schemas.UserPreferencesRead.model_validate(prefs) if prefs else None,
    )


@router.post(
    "/register",
    response_model=schemas.TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit("register", 5, 3600))],
)
async def register(payload: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    """Create user + empty preferences in one transaction.

    The first account with email == ADMIN_EMAIL becomes admin, but only while
    there is no admin yet (e-mail is not verified, so it must not work twice).
    """
    email = payload.email.lower().strip()

    existing_user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing_user:
        # Differentiate deactivated (blocked) vs active (already taken). Deleted
        # users have their row removed entirely, so this branch is hit only when
        # the email still belongs to someone in the system.
        if not existing_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This email belongs to a deactivated account. Contact admin if you believe this is an error.",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    is_admin = False
    if settings.ADMIN_EMAIL and email == settings.ADMIN_EMAIL.lower().strip():
        admins = await db.scalar(select(func.count()).select_from(User).where(User.is_admin))
        is_admin = not admins

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


@router.post(
    "/login",
    response_model=schemas.TokenResponse,
    dependencies=[Depends(limit("login", 10, 300))],
)
async def login(payload: schemas.LoginRequest, db: AsyncSession = Depends(get_db)):
    email = payload.email.lower().strip()
    res = await db.execute(select(User).where(User.email == email))
    user = res.scalar_one_or_none()

    if user and not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account signs in with Google",
        )
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


@router.get("/google/config")
async def google_config():
    """The OAuth client ID for the "Sign in with Google" button (public, not
    a secret); null hides the button."""
    return {"client_id": settings.GOOGLE_CLIENT_ID}


@router.post(
    "/google",
    response_model=schemas.TokenResponse,
    dependencies=[Depends(limit("google", 20, 300))],
)
async def google_sign_in(payload: schemas.GoogleSignInRequest, db: AsyncSession = Depends(get_db)):
    """Sign in or sign up with a Google ID token.

    Found by Google account id, else by e-mail. An existing account with the
    same e-mail is linked, because Google verified the address; its old
    password is switched off, since nobody ever verified who registered it
    (someone could have registered another person's address in advance). The
    user can set a new password in the profile. A new account has no password.
    """
    try:
        ident = await verify_id_token(payload.credential)
    except GoogleTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    user = (await db.execute(select(User).where(User.google_sub == ident.sub))).scalar_one_or_none()
    new_account = password_removed = False
    if user is None:
        user = (await db.execute(select(User).where(User.email == ident.email))).scalar_one_or_none()
        if user is not None:
            if user.google_sub and user.google_sub != ident.sub:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                    detail="This email is linked to another Google account")
            if user.is_active:
                user.google_sub = ident.sub
                if user.hashed_password:
                    user.hashed_password = None
                    password_removed = True
    if user is not None and not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This email belongs to a deactivated account. Contact admin if you believe this is an error.",
        )

    prefs = None
    if user is None:
        is_admin = False
        if settings.ADMIN_EMAIL and ident.email == settings.ADMIN_EMAIL.lower().strip():
            admins = await db.scalar(select(func.count()).select_from(User).where(User.is_admin))
            is_admin = not admins
        user = User(email=ident.email, full_name=(ident.name or "")[:100] or None, hashed_password=None,
                    google_sub=ident.sub, is_admin=is_admin)
        db.add(user)
        await db.flush()
        prefs = UserPreferences(user_id=user.id)
        db.add(prefs)
        new_account = True
    elif not user.full_name and ident.name:
        user.full_name = ident.name[:100]
    db.add(user)
    await db.commit()
    await db.refresh(user)
    if prefs is None:
        prefs = await _load_preferences(db, user.id)
    else:
        await db.refresh(prefs)
    return schemas.TokenResponse(
        access_token=create_access_token(subject=user.id),
        user=_build_user_read(user, prefs),
        new_account=new_account,
        password_removed=password_removed,
    )


@router.get("/me", response_model=schemas.UserRead)
async def me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prefs = await _load_preferences(db, user.id)
    return _build_user_read(user, prefs)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete the authenticated user and all their data."""
    from sqlalchemy import delete
    from app.domain.models import Favorite

    await db.execute(delete(Favorite).where(Favorite.user_id == user.id))
    await db.execute(delete(UserPreferences).where(UserPreferences.user_id == user.id))
    await db.execute(delete(PlanChange).where(PlanChange.user_id == user.id))
    await db.execute(delete(User).where(User.id == user.id))
    await db.commit()


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
    if payload.notification_channels is not None:
        prefs.notification_channels = payload.notification_channels
    if payload.notification_threshold_percent is not None:
        from decimal import Decimal
        prefs.notification_threshold_percent = Decimal(str(payload.notification_threshold_percent))

    await db.commit()
    await db.refresh(prefs)
    return schemas.UserPreferencesRead.model_validate(prefs)


@router.patch(
    "/password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(limit("password", 5, 900))],
)
async def change_password(
    payload: schemas.PasswordChangeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change the authenticated user's password. Verifies current_password
    first; an account without a password (Google only) just sets one."""
    if user.hashed_password and not verify_password(payload.current_password or "", user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must differ from the current one",
        )
    user.hashed_password = hash_password(payload.new_password)
    db.add(user)
    await db.commit()


@router.patch("/profile", response_model=schemas.UserRead)
async def update_profile(
    payload: schemas.ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the authenticated user's display name."""
    user.full_name = (payload.full_name or "").strip() or None
    db.add(user)
    await db.commit()
    await db.refresh(user)
    prefs = await _load_preferences(db, user.id)
    return _build_user_read(user, prefs)
