"""Password hashing (bcrypt) + JWT access tokens (HS256)."""
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt import PyJWTError as JWTError
from passlib.context import CryptContext

from app.core.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def _secret() -> str:
    if len(settings.JWT_SECRET) < 32:
        raise RuntimeError("JWT_SECRET is missing or shorter than 32 characters")
    return settings.JWT_SECRET


def create_access_token(subject: str | int, extra_claims: dict[str, Any] | None = None) -> str:
    """Encode a JWT with `sub` = user id (stringified) and expiry."""
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)).timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, _secret(), algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Return payload dict if valid, else None."""
    try:
        return jwt.decode(token, _secret(), algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
