"""Fixed-window request limits in Redis, keyed by client IP.

Used on the public auth endpoints and the AI chat so nobody can guess
passwords, mass-register accounts or burn the Gemini quota.
"""
import redis.asyncio as aioredis
from fastapi import HTTPException, Request, status

from app.core.config import settings

_redis = aioredis.from_url(settings.REDIS_URL)


def limit(name: str, times: int, seconds: int):
    """Dependency: at most `times` calls per `seconds` per client IP."""
    async def dep(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        key = f"marketpulse:rl:{name}:{ip}"
        try:
            n = await _redis.incr(key)
            if n == 1:
                await _redis.expire(key, seconds)
        except Exception:
            return  # Redis down: do not lock everyone out
        if n > times:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests, try again later",
            )
    return dep
