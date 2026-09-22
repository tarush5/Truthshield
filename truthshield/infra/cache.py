"""
Redis cache.

Degrades to a bounded in-process dict when Redis is unreachable. That is a
deliberate exception to this codebase's fail-closed stance: a cache miss is
always safe, so losing Redis should slow the service rather than stop it. It
is the *database* fallback that was dangerous, because a silent switch to
local SQLite meant accepting writes nobody would ever read again.

The degradation is logged once and surfaced on /health, so it cannot go
unnoticed.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Optional

from truthshield.settings import get_settings

logger = logging.getLogger(__name__)


class _LocalCache:
    """Bounded TTL dict used only when Redis is unavailable."""

    def __init__(self, max_entries: int = 512):
        self._data: "OrderedDict[str, tuple[float, str]]" = OrderedDict()
        self._max = max_entries
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            entry = self._data.get(key)
            if not entry:
                return None
            expires_at, value = entry
            if expires_at < time.time():
                self._data.pop(key, None)
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key: str, value: str, ttl: int) -> None:
        with self._lock:
            self._data[key] = (time.time() + ttl, value)
            self._data.move_to_end(key)
            while len(self._data) > self._max:
                self._data.popitem(last=False)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class Cache:
    """Thin JSON cache over Redis, with a local fallback."""

    def __init__(self):
        self._settings = get_settings()
        self._local = _LocalCache()
        self._redis = None
        self._degraded = False
        self._connect()

    def _connect(self) -> None:
        try:
            import redis
            client = redis.Redis.from_url(
                self._settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                health_check_interval=30,
            )
            client.ping()
            self._redis = client
            self._degraded = False
            logger.info("Redis cache connected")
        except Exception as exc:
            self._redis = None
            self._degraded = True
            logger.warning(
                "Redis unavailable (%s). Falling back to an in-process cache: "
                "entries will not be shared between workers and are lost on restart.",
                exc,
            )

    @property
    def degraded(self) -> bool:
        return self._degraded

    @property
    def backend(self) -> str:
        return "redis" if self._redis is not None else "in-process"

    def get(self, key: str) -> Optional[Any]:
        raw = None
        if self._redis is not None:
            try:
                raw = self._redis.get(key)
            except Exception as exc:
                logger.warning("Redis read failed, using local cache: %s", exc)
                self._degraded = True
                raw = self._local.get(key)
        else:
            raw = self._local.get(key)

        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            # A corrupt entry must never take down a request.
            self.delete(key)
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        ttl = ttl or self._settings.CACHE_TTL_SECONDS
        try:
            raw = json.dumps(value, default=str)
        except (TypeError, ValueError) as exc:
            logger.debug("Value for %s is not serialisable, not cached: %s", key, exc)
            return

        if self._redis is not None:
            try:
                self._redis.setex(key, ttl, raw)
                return
            except Exception as exc:
                logger.warning("Redis write failed, using local cache: %s", exc)
                self._degraded = True
        self._local.set(key, raw, ttl)

    def delete(self, key: str) -> None:
        if self._redis is not None:
            try:
                self._redis.delete(key)
            except Exception:
                pass
        self._local.delete(key)

    def health(self) -> dict:
        return {"backend": self.backend, "degraded": self._degraded}


_cache: Optional[Cache] = None
_cache_lock = threading.Lock()


def get_cache() -> Cache:
    global _cache
    if _cache is None:
        with _cache_lock:
            if _cache is None:
                _cache = Cache()
    return _cache
