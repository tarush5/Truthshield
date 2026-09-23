"""
Cross-cutting HTTP concerns: request identity and response hardening.

Both are pure middleware and hold no state, so they are safe under the
threaded worker model and add no per-request allocation worth measuring.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# The id of the request being served on this task. A ContextVar rather than a
# thread-local: the app is async, so several requests share a thread and a
# thread-local would hand one request's id to another.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# Echoed back, and accepted from a trusted proxy so one id spans the whole
# hop chain rather than changing at each service boundary.
REQUEST_ID_HEADER = "X-Request-ID"

# An inbound id is used only if it looks like one. Without this, an attacker
# controls a value that lands in every log line for their request, which is
# how log injection and forged correlation get in.
MAX_REQUEST_ID = 64

# Anything past this is worth an operator's attention even when it succeeded.
SLOW_REQUEST_SECONDS = 5.0


def current_request_id() -> str:
    """The id of the request being handled, or "-" outside a request."""
    return request_id_var.get()


def _clean(value: str) -> str:
    """Keep an inbound id only if it is plausibly one."""
    value = (value or "").strip()
    if not value or len(value) > MAX_REQUEST_ID:
        return ""
    # Printable ASCII without whitespace or control characters: enough for a
    # uuid or a trace id, not enough to forge a log line.
    if not all(33 <= ord(c) <= 126 for c in value):
        return ""
    return value


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Give every request an id, log how it went, and hand the id back.

    The id is what makes a user's "it failed at 2pm" answerable. It is
    returned on the response so a reader can quote it, and it is on the log
    line so the quote finds the request.
    """

    async def dispatch(self, request, call_next):
        request_id = _clean(request.headers.get(REQUEST_ID_HEADER)) or uuid.uuid4().hex[:16]
        token = request_id_var.set(request_id)
        request.state.request_id = request_id

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Logged here with the id attached, then re-raised for the app's
            # own handler to turn into a response. The handler cannot log
            # the duration, because it does not know when this started.
            elapsed = time.perf_counter() - started
            logger.exception(
                "%s %s failed after %.3fs [%s]",
                request.method, request.url.path, elapsed, request_id,
            )
            raise
        finally:
            request_id_var.reset(token)

        elapsed = time.perf_counter() - started
        response.headers[REQUEST_ID_HEADER] = request_id
        # Exposed explicitly: a browser cannot read a non-safelisted header
        # on a cross-origin response otherwise, which is exactly the case
        # here, and the id would be invisible to the client that needs it.
        response.headers["Access-Control-Expose-Headers"] = REQUEST_ID_HEADER

        if elapsed >= SLOW_REQUEST_SECONDS:
            logger.warning(
                "Slow: %s %s took %.2fs [%s]",
                request.method, request.url.path, elapsed, request_id,
            )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Response headers that close off whole categories of attack.

    Scoped to what this service actually is. It serves JSON and, outside
    production, an interactive docs page; it is not a web app, so the policy
    can be far stricter than a site's would be.
    """

    def __init__(self, app: ASGIApp, *, https_only: bool = False, docs_paths: tuple = ()):
        super().__init__(app)
        self._https_only = https_only
        self._docs_paths = docs_paths

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path

        # Content sniffing is how a JSON response with attacker-controlled
        # content gets executed as script.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        # This API has no use for any of them, and the default is to allow.
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()",
        )

        if any(path.startswith(p) for p in self._docs_paths):
            # Swagger and ReDoc load their bundle from a CDN and run inline
            # scripts, so they need their own policy. These paths are off in
            # production; this keeps them usable everywhere else without
            # loosening the policy on the routes that carry data.
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https://fastapi.tiangolo.com; "
                "worker-src 'self' blob:; "
                "frame-ancestors 'none'",
            )
        else:
            # A JSON endpoint needs to load nothing at all.
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
            )

        if self._https_only:
            # Only ever sent over HTTPS. Setting it on a plain-HTTP
            # deployment would lock clients out of a service that has no TLS
            # to fall back to.
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )

        return response
