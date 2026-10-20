"""
Rate limiting.

One limiter, created here rather than in `main.py`, so routers can attach
stricter per-route limits without importing the application module.

1.x defined `RATE_LIMIT_AUTH` and never applied it, leaving sign-in guarded
only by the global per-IP limit. `auth_limit` is that limit, actually attached.
"""

from __future__ import annotations

import logging

from truthshield.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

def client_key(request, fallback) -> str:
    """
    Who a request counts against: the account when it carries a valid access
    token, otherwise the client address.

    Keyed on the address alone, every user behind one proxy or office NAT
    shared a single allowance: two accounts on one address got 20 analyses a
    minute between them, not each. The token's signature is verified, so the
    user id cannot be forged to spread one client across many keys.
    """
    header = request.headers.get("authorization") or ""
    if header[:7].lower() == "bearer ":
        from truthshield.services import auth

        payload = auth.decode_token(header[7:].strip())
        if payload and payload.get("sub"):
            return f"user:{payload['sub']}"
    return fallback(request)


try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    limiter = Limiter(key_func=lambda request: client_key(request, get_remote_address),
                      default_limits=[settings.RATE_LIMIT])
except ImportError:  # pragma: no cover - slowapi is a hard requirement
    limiter = None
    logger.error("slowapi is not installed — the API is running WITHOUT rate limiting")


def auth_limit(func):
    """The stricter limit for credential-handling endpoints."""
    if limiter is None:
        return func
    return limiter.limit(settings.RATE_LIMIT_AUTH)(func)


def expensive_limit(func):
    """Analysis endpoints that run the full pipeline inline."""
    if limiter is None:
        return func
    return limiter.limit(settings.RATE_LIMIT_ANALYSIS)(func)
