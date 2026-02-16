"""BetterAuth JWT verification and conditional auth for FastAPI."""

import os
import time
import logging
import threading
from typing import Annotated

import httpx
import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, Request

log = logging.getLogger("cmk")

_jwk_client: PyJWKClient | None = None
_jwk_cache_time: float = 0
_JWK_CACHE_TTL = 3600  # 1 hour
_jwk_lock = threading.Lock()


def is_auth_enabled() -> bool:
    """Check if BetterAuth is configured (URL + secret)."""
    url = os.getenv("BETTER_AUTH_URL", "")
    secret = os.getenv("BETTER_AUTH_SECRET", "")
    if not url or url.startswith("<"):
        return False
    if not secret or secret.startswith("<"):
        return False
    return True


def _get_jwks_url() -> str:
    """Build the JWKS endpoint from BETTER_AUTH_URL."""
    base = os.getenv("BETTER_AUTH_URL", "").rstrip("/")
    if not base:
        return ""
    return f"{base}/api/auth/jwks"


def _get_jwk_client() -> PyJWKClient | None:
    global _jwk_client, _jwk_cache_time
    now = time.time()
    if _jwk_client and (now - _jwk_cache_time) < _JWK_CACHE_TTL:
        return _jwk_client

    url = _get_jwks_url()
    if not url:
        return None

    with _jwk_lock:
        # Double-check after acquiring lock
        if _jwk_client and (time.time() - _jwk_cache_time) < _JWK_CACHE_TTL:
            return _jwk_client
        try:
            _jwk_client = PyJWKClient(url, cache_keys=True)
            _jwk_cache_time = time.time()
            return _jwk_client
        except Exception as e:
            log.warning("failed to fetch JWKS: %s", e)
            return None


def verify_jwt_token(token: str) -> dict | None:
    """Verify a BetterAuth JWT and return claims (sub, email, name)."""
    client = _get_jwk_client()
    if not client:
        return None

    try:
        signing_key = client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "EdDSA"],
            options={"verify_aud": False},
        )
        return {
            "id": claims.get("sub", ""),
            "email": claims.get("email", ""),
            "name": claims.get("name", ""),
        }
    except jwt.ExpiredSignatureError:
        log.debug("jwt token expired")
        return None
    except jwt.InvalidTokenError as e:
        log.debug("jwt token invalid: %s", e)
        return None


LOCAL_USER = {"id": "local", "email": None, "name": "", "plan": "free"}


def _extract_bearer(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


async def get_current_user(
    request: Request, db=None
) -> dict:
    """FastAPI dependency. Returns user dict or raises 401.

    If BetterAuth is not configured, returns local user (no auth needed).
    Tries API key first (cmk-sk-...), then BetterAuth JWT.
    """
    if not is_auth_enabled():
        return LOCAL_USER

    token = _extract_bearer(request)
    if not token:
        raise HTTPException(401, "authorization required")

    # Try API key first (cmk-sk-...)
    if token.startswith("cmk-sk-"):
        from .auth_keys import validate_api_key
        result = validate_api_key(token, db)
        if result:
            return result
        raise HTTPException(401, "invalid API key")

    # Try BetterAuth JWT
    claims = verify_jwt_token(token)
    if not claims:
        raise HTTPException(401, "invalid token")

    # Upsert user on first auth
    if db:
        db.upsert_user(
            claims["id"], claims.get("email"), claims.get("name", "")
        )

    user = {
        "id": claims["id"],
        "email": claims.get("email"),
        "name": claims.get("name", ""),
        "plan": "free",
        "teams": [],
    }
    if db:
        stored = db.get_user(claims["id"])
        if stored:
            user["plan"] = stored.get("plan", "free")
        user["teams"] = db.list_user_teams(claims["id"])

    return user


async def optional_auth(request: Request) -> dict | None:
    """Same as get_current_user but returns None if no token."""
    if not is_auth_enabled():
        return LOCAL_USER

    token = _extract_bearer(request)
    if not token:
        return None

    try:
        return await get_current_user(request)
    except HTTPException:
        return None
