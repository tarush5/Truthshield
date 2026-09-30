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

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT])
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
