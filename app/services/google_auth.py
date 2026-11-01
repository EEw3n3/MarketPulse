"""Check a "Sign in with Google" ID token (Google Identity Services).

The browser gets a signed JWT from Google and posts it to /auth/google. It is
accepted only when Google's key signed it, it was issued for our client ID,
has not expired, and Google says the e-mail is verified. Google's public keys
are fetched from GOOGLE_CERTS and cached.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

import jwt
from jwt import PyJWKClient

from app.core.config import settings

GOOGLE_CERTS = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ("accounts.google.com", "https://accounts.google.com")

_jwks: Optional[PyJWKClient] = None


class GoogleTokenError(ValueError):
    pass


@dataclass
class GoogleIdentity:
    sub: str
    email: str
    name: Optional[str]


def _client() -> PyJWKClient:
    global _jwks
    if _jwks is None:
        _jwks = PyJWKClient(GOOGLE_CERTS, cache_keys=True, lifespan=6 * 3600, timeout=10)
    return _jwks


def _verify(token: str, client_id: str) -> GoogleIdentity:
    try:
        key = _client().get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=["RS256"], audience=client_id,
                            options={"require": ["exp", "iat", "aud", "iss", "sub"]}, leeway=60)
    except jwt.PyJWTError as e:
        raise GoogleTokenError(f"invalid Google token: {e}") from e
    if claims.get("iss") not in ISSUERS:
        raise GoogleTokenError("token not issued by Google")
    email = (claims.get("email") or "").lower().strip()
    if not email or claims.get("email_verified") is not True:
        raise GoogleTokenError("Google has not verified this e-mail")
    return GoogleIdentity(sub=str(claims["sub"]), email=email, name=(claims.get("name") or None))


async def verify_id_token(token: str) -> GoogleIdentity:
    if not settings.GOOGLE_CLIENT_ID:
        raise GoogleTokenError("Google sign-in is not configured")
    # The key fetch is blocking network I/O.
    return await asyncio.to_thread(_verify, token, settings.GOOGLE_CLIENT_ID)
