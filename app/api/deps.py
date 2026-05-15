from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
from app.core.security import decode_access_token
from app.domain.models import User

# tokenUrl is informational (used by Swagger UI); our actual login is /auth/login
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def get_current_user(
    token: str | None = Depends(_oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Decode JWT, load user, reject inactive accounts."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exc

    payload = decode_access_token(token)
    if not payload:
        raise credentials_exc

    sub = payload.get("sub")
    if not sub:
        raise credentials_exc

    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        raise credentials_exc

    user = await db.get(User, user_id)
    if not user:
        raise credentials_exc
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account disabled",
        )
    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """Require is_admin=True; otherwise 403."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user


from fastapi import Header  # noqa: E402

from app.core.config import settings  # noqa: E402


async def get_worker(authorization: str | None = Header(default=None)) -> bool:
    """Auth for the distributed scrape worker — Bearer <WORKER_TOKEN>.

    Worker token is a long random shared secret in env on both the server and
    the local worker machine. NOT a JWT — this is a long-lived service token.
    """
    if not settings.WORKER_TOKEN:
        raise HTTPException(503, "Worker integration is not configured (WORKER_TOKEN env missing)")
    if authorization != f"Bearer {settings.WORKER_TOKEN}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid worker credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True
