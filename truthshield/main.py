"""
Application entry point.

Startup is deliberately noisy about what is and is not available. The previous
version logged "Rate limiting enabled" while the limiter was attached to no
route, and reported a healthy service while silently running on a fallback
SQLite file. Anything degraded here says so, on startup and on /health.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from truthshield.api.routes import analysis_router, auth_router, meta_router
from truthshield.api.stream import stream_router
from truthshield.settings import get_settings

settings = get_settings()

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("truthshield")


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio

    from truthshield.detectors.registry import availability
    from truthshield.infra.cache import get_cache
    from truthshield.infra.celery_app import broker_reachable
    from truthshield.infra.database import check_connection

    logger.info("TruthShield %s — %s", app.version, settings.APP_ENV.value)

    db_ok = check_connection()
    logger.info("Database: %s", "connected" if db_ok else "UNREACHABLE")
    if not db_ok and settings.APP_ENV.is_production:
        # Fail loudly rather than serve requests that cannot be persisted.
        raise RuntimeError("Database is unreachable; refusing to start in production.")

    cache = get_cache()
    logger.info("Cache: %s%s", cache.backend, " (degraded)" if cache.degraded else "")
    logger.info("Celery broker: %s", "reachable" if broker_reachable() else "UNREACHABLE")

    caps = availability()
    missing = [k for k, v in caps.items() if v is False]
    logger.info("Detector capabilities: %s", caps)
    if missing:
        logger.warning(
            "Unavailable capabilities: %s. Analyses will report these as "
            "unchecked rather than passing.", ", ".join(missing),
        )

    async def warm():
        """Load the NLP pipeline and warm caches off the request path."""
        def _load():
            try:
                from truthshield.domain.verdict.claim_extractor import ClaimExtractor
                ClaimExtractor().extract("Warmup sentence for model loading.", "en")
                from truthshield.infra.evidence.retriever import EvidenceRetriever
                EvidenceRetriever._get_session()
                EvidenceRetriever._rss_entries()
                logger.info("Warmup complete")
            except Exception as exc:
                logger.warning("Warmup failed (non-fatal): %s", exc)
        await asyncio.to_thread(_load)

    asyncio.create_task(warm())
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="TruthShield API",
    description=(
        "Misinformation analysis: claim extraction, evidence retrieval, "
        "stance detection and manipulation checks. Reports state what was "
        "checked and what could not be."
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=5)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,   # validated: never "*"
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

# ── Rate limiting ─────────────────────────────────────────────
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from slowapi.util import get_remote_address

    limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    # The middleware is what actually applies default_limits. Without it the
    # limiter exists and enforces nothing.
    app.add_middleware(SlowAPIMiddleware)
    logger.info("Rate limiting: %s on every route", settings.RATE_LIMIT)
except ImportError:
    logger.error("slowapi is not installed — the API is running WITHOUT rate limiting")


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    """
    Never leak internals.

    The previous API returned exception text in `detail`, which described the
    token verification setup to anyone who sent a malformed token.
    """
    logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


app.include_router(auth_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")
app.include_router(stream_router, prefix="/api/v1")
app.include_router(meta_router, prefix="/api/v1")


@app.get("/", tags=["meta"])
def root():
    return {
        "service": "TruthShield",
        "version": app.version,
        "docs": "/docs",
        "health": "/api/v1/health",
    }
