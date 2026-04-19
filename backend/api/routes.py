"""
TruthShield — API Routes
FastAPI REST endpoints for content analysis, reporting, and feedback.
"""

import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.config import get_settings
from backend.models.schemas import (
    AnalysisReport,
    AnalyzeRequest,
    ContentType,
    FeedbackRequest,
    StatsResponse,
    Verdict,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ── In-memory store (replace with PostgreSQL in production) ───
reports_store: dict = {}
feedback_store: list = []
stats_data = {
    "total_analyses": 0,
    "verdicts": {"TRUE": 0, "FALSE": 0, "MISLEADING": 0, "UNVERIFIED": 0},
    "language_distribution": {"en": 0, "hi": 0, "ta": 0},
    "flagged_domains": {},
}


async def run_analysis_pipeline(
    text: Optional[str] = None,
    file_path: Optional[str] = None,
    url: Optional[str] = None,
    content_type: ContentType = ContentType.TEXT,
    lang: str = "en",
    progress_callback = None,
) -> AnalysisReport:
    """
    Run the full analysis pipeline on content.

    Delegates to DecisionPipeline — a 5-stage gate-based orchestrator
    with cross-signal aggregation and Bayesian confidence scoring.
    """
    from backend.pipeline.decision_pipeline import DecisionPipeline

    pipeline = DecisionPipeline()
    report = await pipeline.execute(
        text=text,
        file_path=file_path,
        url=url,
        content_type=content_type,
        lang=lang,
        progress_callback=progress_callback,
    )

    # Store report
    reports_store[report.id] = report

    # Update stats
    stats_data["total_analyses"] += 1
    stats_data["language_distribution"][report.language.value] = (
        stats_data["language_distribution"].get(report.language.value, 0) + 1
    )
    if report.claims:
        for cv in report.claims:
            stats_data["verdicts"][cv.verdict.value] = (
                stats_data["verdicts"].get(cv.verdict.value, 0) + 1
            )

    return report


@router.post("/analyze", response_model=AnalysisReport)
async def analyze_content(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    lang: str = Form("en"),
):
    """
    Analyze content for misinformation.
    Accepts multipart form with file, URL, or text.
    """
    settings = get_settings()

    content_type = ContentType.TEXT
    file_path = None

    if file:
        # Determine content type from file extension
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            content_type = ContentType.IMAGE
        elif ext in (".mp3", ".wav", ".ogg", ".m4a", ".flac"):
            content_type = ContentType.AUDIO
        elif ext in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
            content_type = ContentType.VIDEO
        else:
            content_type = ContentType.TEXT

        # Save uploaded file
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        file_path = str(settings.UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}")
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # If text file, read its content
        if content_type == ContentType.TEXT:
            text = content.decode("utf-8", errors="ignore")

    elif url:
        content_type = ContentType.URL
    elif text:
        content_type = ContentType.TEXT
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one of: file, url, or text",
        )

    report = await run_analysis_pipeline(
        text=text,
        file_path=file_path,
        url=url,
        content_type=content_type,
        lang=lang,
    )

    return report


@router.get("/report/{report_id}", response_model=AnalysisReport)
async def get_report(report_id: str):
    """Retrieve a full analysis report by ID."""
    report = reports_store.get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.post("/feedback")
async def submit_feedback(feedback: FeedbackRequest):
    """Submit crowdsourced feedback on a report."""
    if feedback.report_id not in reports_store:
        raise HTTPException(status_code=404, detail="Report not found")

    feedback_store.append(feedback.model_dump())
    logger.info(f"Feedback received for report {feedback.report_id}: {feedback.user_verdict}")

    return {"status": "ok", "message": "Feedback recorded. Thank you!"}


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Get aggregated dashboard statistics."""
    # Compute top flagged domains
    domain_list = [
        {"domain": domain, "count": count}
        for domain, count in sorted(
            stats_data["flagged_domains"].items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]
    ]

    avg_trust = 50.0
    if reports_store:
        scores = [r.credibility.trust_score for r in reports_store.values()]
        avg_trust = sum(scores) / len(scores)

    return StatsResponse(
        total_analyses=stats_data["total_analyses"],
        verdicts=stats_data["verdicts"],
        language_distribution=stats_data["language_distribution"],
        top_flagged_domains=domain_list,
        avg_trust_score=round(avg_trust, 1),
    )


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0", "service": "TruthShield"}
