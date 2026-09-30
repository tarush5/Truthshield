"""
One error shape for the whole API.

    {"error": {"code": "NOT_FOUND", "message": "...", "request_id": "..."},
     "detail": "..."}

`error` is the 2.0 contract. `detail` is kept because every 1.x client --
and the 1.x test-suite -- reads it; dropping it would be a breaking change
for no benefit. Stack traces are never included; the request id is the
thread an operator pulls to find the full failure in the logs.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from truthshield.api.middleware import current_request_id

DEFAULT_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    503: "UNAVAILABLE",
}


class ApiError(HTTPException):
    """An HTTPException that carries a stable machine-readable code."""

    def __init__(self, status_code: int, code: str, message: str, headers: Optional[dict] = None):
        super().__init__(status_code=status_code, detail=message, headers=headers)
        self.code = code


def envelope(status: int, message: str, *, code: Optional[str] = None, detail: Any = None,
             headers: Optional[dict] = None) -> JSONResponse:
    request_id = current_request_id()
    body = {
        "error": {
            "code": code or DEFAULT_CODES.get(status, "ERROR"),
            "message": message,
            "request_id": request_id,
        },
        "detail": detail if detail is not None else message,
    }
    merged = {"X-Request-ID": request_id, **(headers or {})}
    return JSONResponse(status_code=status, content=body, headers=merged)


async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return envelope(
        exc.status_code, message,
        code=getattr(exc, "code", None),
        detail=exc.detail,
        headers=getattr(exc, "headers", None),
    )


async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    first = errors[0] if errors else {}
    field = ".".join(str(p) for p in first.get("loc", [])[1:]) or "request"
    message = f"Invalid {field}: {first.get('msg', 'invalid value')}"
    # `detail` keeps FastAPI's field list, which 1.x clients render.
    safe = [{"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")} for e in errors]
    return envelope(422, message, code="VALIDATION_ERROR", detail=safe)


async def rate_limited(request: Request, exc) -> JSONResponse:
    return envelope(
        429, "Too many requests. Please wait a moment and try again.",
        code="RATE_LIMITED", headers={"Retry-After": "60"},
    )


def register(app) -> None:
    app.add_exception_handler(StarletteHTTPException, http_error)
    app.add_exception_handler(RequestValidationError, validation_error)
