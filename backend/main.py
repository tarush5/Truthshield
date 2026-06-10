"""
TruthShield — FastAPI Application Entry Point
Main application with CORS, rate limiting, and route mounting.
"""

import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.api.routes import router as api_router
from backend.api.websocket import ws_router

# ── Settings (Initialize Once) ────────────────────────────────
settings = get_settings()

# ── Logging Setup ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("truthshield")


async def start_realtime_ingestion_simulation():
    """Periodically simulate social ingestion feeds, analyze them, and store in trending_misinfo."""
    import asyncio
    from backend.models.db import SessionLocal, TrendingMisinfo
    from backend.pipeline.decision_pipeline import DecisionPipeline
    
    # Wait a little bit after startup to avoid blocking initial API readiness
    await asyncio.sleep(5)
    
    mock_feed = [
        {"claim": "New study claims drinking coffee cures COVID-19 within 24 hours.", "platform": "Twitter", "virality": 9.4},
        {"claim": "Government to impose 50% tax on all digital transactions starting next week.", "platform": "Reddit", "virality": 8.7},
        {"claim": "Leaked video shows UFO landing in London outskirts yesterday morning.", "platform": "RSS", "virality": 7.2},
        {"claim": "World health experts recommend bananas as 100% cure for influenza.", "platform": "Twitter", "virality": 5.1},
    ]
    
    pipeline = DecisionPipeline()
    while True:
        db = SessionLocal()
        try:
            for item in mock_feed:
                exists = db.query(TrendingMisinfo).filter(TrendingMisinfo.claim == item["claim"]).first()
                if exists:
                    continue
                    
                report = await pipeline.execute(text=item["claim"])
                
                # If verdict is FALSE or MISLEADING, flag it and add to trending misinfo table
                if report.credibility.verdict in ("FALSE", "MISLEADING"):
                    trending = TrendingMisinfo(
                        claim=item["claim"],
                        verdict=report.credibility.verdict,
                        confidence=report.credibility.trust_score / 100.0,
                        source_platform=item["platform"],
                        virality_score=item["virality"]
                    )
                    db.add(trending)
            db.commit()
            logger.info("Real-time ingestion simulation task completed successfully.")
        except Exception as e:
            logger.warning(f"Real-time monitor simulation encountered error: {e}")
        finally:
            db.close()
            
        # Sleep for 5 minutes before polling again
        await asyncio.sleep(300)


# ── Lifespan Events (Startup & Shutdown) ──────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown events."""

    # Ensure required directories exist
    from backend.models import init_db
    init_db()

    if getattr(settings, "UPLOAD_DIR", None):
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    if getattr(settings, "MODEL_CACHE_DIR", None):
        os.makedirs(settings.MODEL_CACHE_DIR, exist_ok=True)

    # Start real-time monitoring simulation task in background
    import asyncio
    asyncio.create_task(start_realtime_ingestion_simulation())

    logger.info("=" * 60)
    logger.info("  TruthShield — AI Misinformation Response System")
    logger.info(f"  Environment: {settings.APP_ENV}")
    logger.info(f"  API: http://{settings.APP_HOST}:{settings.APP_PORT}")
    logger.info(f"  Docs: http://{settings.APP_HOST}:{settings.APP_PORT}/docs")
    logger.info("=" * 60)

    yield

    logger.info("TruthShield shutting down...")


# ── FastAPI App Initialization ────────────────────────────────
app = FastAPI(
    title="TruthShield API",
    description=(
        "AI-powered misinformation detection and fact-verification system. "
        "Supports text, image, audio, video, and URL analysis in English, Hindi, and Tamil."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS Middleware ───────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=getattr(settings, "cors_origins_list", ["*"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate Limiting (Optional, Safe) ────────────────────────────
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[getattr(settings, "RATE_LIMIT", "100/minute")],
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    logger.info(f"Rate limiting enabled: {settings.RATE_LIMIT}")

except ImportError:
    logger.warning("Rate limiting disabled: slowapi not installed")


# ── Routes ────────────────────────────────────────────────────
app.include_router(api_router, prefix="/api/v1", tags=["Analysis"])
app.include_router(ws_router, tags=["WebSocket"])


# ── Root Endpoint ─────────────────────────────────────────────
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint — API information."""
    return {
        "service": "TruthShield",
        "version": "1.0.0",
        "description": "AI Misinformation Response System",
        "docs": "/docs",
        "endpoints": {
            "analyze": "POST /api/v1/analyze",
            "report": "GET /api/v1/report/{id}",
            "feedback": "POST /api/v1/feedback",
            "stats": "GET /api/v1/stats",
            "websocket": "WS /ws/analyze",
            "health": "GET /api/v1/health",
        },
        "supported_languages": ["en", "hi", "ta"],
        "supported_content_types": ["text", "image", "audio", "video", "url"],
    }


# ── Entry Point ───────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.APP_ENV == "development",
        log_level="info",
    )