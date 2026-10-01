"""
Resilience for external calls: timeouts, retries with backoff, circuit breakers.

External services fail, and a failing one must degrade the result it feeds
-- "evidence unavailable from this provider" -- rather than stall every
request behind it. A breaker opens after repeated failures and fails fast
for a cooling-off period, so a dead provider costs one timeout per window
instead of one per request.

Never invents a result: when every attempt fails, the caller gets the
exception (or the declared fallback value) and reports the gap.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from typing import Callable, Dict, Optional, Tuple, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitOpenError(RuntimeError):
    """Raised instead of calling a provider whose breaker is open."""


class CircuitBreaker:
    def __init__(self, name: str, *, failure_threshold: int = 5, reset_after: float = 60.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_after = reset_after
        self._failures = 0
        self._opened_at: Optional[float] = None
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            if self._opened_at is None:
                return "closed"
            if time.monotonic() - self._opened_at >= self.reset_after:
                return "half_open"
            return "open"

    def before_call(self) -> None:
        if self.state == "open":
            raise CircuitOpenError(f"{self.name} is temporarily disabled after repeated failures")

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                if self._opened_at is None:
                    logger.warning("Circuit for %s opened after %d failures", self.name, self._failures)
                self._opened_at = time.monotonic()

    def snapshot(self) -> dict:
        return {"name": self.name, "state": self.state, "failures": self._failures}


_BREAKERS: Dict[str, CircuitBreaker] = {}
_REGISTRY_LOCK = threading.Lock()


def breaker(name: str, **kwargs) -> CircuitBreaker:
    with _REGISTRY_LOCK:
        if name not in _BREAKERS:
            _BREAKERS[name] = CircuitBreaker(name, **kwargs)
        return _BREAKERS[name]


def all_breakers() -> list:
    return [b.snapshot() for b in _BREAKERS.values()]


def call_with_retry(
    fn: Callable[[], T],
    *,
    name: str,
    attempts: int = 3,
    base_delay: float = 0.4,
    retry_on: Tuple[Type[BaseException], ...] = (Exception,),
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """
    Call `fn` with exponential backoff and jitter, behind the named breaker.

    Only exceptions in `retry_on` are retried; anything else propagates at
    once (a 400 will not succeed on the third try).
    """
    circuit = breaker(name)
    circuit.before_call()
    last: Optional[BaseException] = None
    for attempt in range(attempts):
        try:
            result = fn()
            circuit.record_success()
            return result
        except retry_on as exc:
            last = exc
            circuit.record_failure()
            if attempt == attempts - 1 or circuit.state == "open":
                break
            delay = base_delay * (2 ** attempt) * (0.8 + random.random() * 0.4)
            logger.info("%s failed (%s); retrying in %.2fs", name, type(exc).__name__, delay)
            sleep(delay)
    assert last is not None
    raise last
