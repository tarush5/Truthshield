"""
TruthShield — API Routes
FastAPI REST endpoints for content analysis, reporting, and feedback.
"""

import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Depends
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models import (
    AnalysisReport,
    AnalyzeRequest,
    ContentType,
    FeedbackRequest,
    StatsResponse,
    Verdict,
    get_db,
)
from backend.api.auth import get_current_user, require_user, CurrentUser

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


# Temporary in-memory OTP store
otp_store = {}


@router.post("/auth/otp")
async def send_otp(email_data: dict, db: Session = Depends(get_db)):
    """Send OTP to the user's email."""
    email = email_data.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
        
    import random
    otp = str(random.randint(100000, 999999))
    otp_store[email] = otp
    
    # In development, print to console
    logger.info("=" * 40)
    logger.info(f"  OTP for {email}: {otp}")
    logger.info("=" * 40)
    
    return {"status": "ok", "message": f"OTP sent to {email} (Check backend console logs)"}


@router.post("/auth/verify")
async def verify_otp(verify_data: dict, db: Session = Depends(get_db)):
    """Verify OTP and generate a JWT token."""
    email = verify_data.get("email")
    token = verify_data.get("token")
    
    if not email or not token:
        raise HTTPException(status_code=400, detail="Email and OTP token are required")
        
    expected_otp = otp_store.get(email)
    if not expected_otp or expected_otp != token:
        # Dev override to allow easy local verification
        if token != "123456":
            raise HTTPException(status_code=400, detail="Invalid OTP")
            
    # Auto-create user in database
    from backend.models.db import User
    db_user = db.query(User).filter(User.email == email).first()
    if not db_user:
        db_user = User(email=email)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
    # Generate JWT token
    from jose import jwt
    from datetime import datetime, timedelta
    
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
    payload = {
        "sub": str(db_user.id),
        "email": db_user.email,
        "exp": expire
    }
    access_token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(db_user.id),
            "email": db_user.email
        }
    }


@router.post("/analyze", response_model=AnalysisReport)
async def analyze_content(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    lang: str = Form("en"),
    db: Session = Depends(get_db),
    current_user: Optional[CurrentUser] = Depends(get_current_user),
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

    # Save to Database
    from backend.models.db import Report as ReportDB, EvidenceDB
    try:
        user_uuid = uuid.UUID(current_user.id) if current_user else None
        db_report = ReportDB(
            id=report.id,
            user_id=user_uuid,
            content_type=report.content_type.value,
            input_text=report.original_text,
            verdict=report.credibility.verdict,
            confidence=report.credibility.trust_score / 100.0,
        )
        db.add(db_report)

        # Save evidence
        if report.claims:
            for claim_verdict in report.claims:
                for ev in claim_verdict.evidence:
                    db_ev = EvidenceDB(
                        report_id=report.id,
                        source_url=ev.url,
                        source_name=ev.title,
                        credibility_score=ev.source_score,
                    )
                    db.add(db_ev)
        db.commit()
    except Exception as e:
        logger.warning(f"Failed to persist report to DB: {e}")

    return report


@router.get("/report/{report_id}", response_model=AnalysisReport)
async def get_report(report_id: str, db: Session = Depends(get_db)):
    """Retrieve a full analysis report by ID."""
    report = reports_store.get(report_id)
    if not report:
        from backend.models.db import Report as ReportDB
        db_report = db.query(ReportDB).filter(ReportDB.id == report_id).first()
        if not db_report:
            raise HTTPException(status_code=404, detail="Report not found")
        
        # Reconstruct AnalysisReport from db_report
        from backend.models.schemas import CredibilityScore, Evidence
        evidence_list = [
            Evidence(
                title=ev.source_name or "",
                url=ev.source_url,
                snippet="",
                source_score=ev.credibility_score,
            )
            for ev in db_report.evidence
        ]
        
        report = AnalysisReport(
            id=db_report.id,
            content_type=ContentType(db_report.content_type),
            original_text=db_report.input_text,
            credibility=CredibilityScore(
                trust_score=int(db_report.confidence * 100),
                verdict=db_report.verdict,
            ),
        )
    return report


@router.post("/feedback")
async def submit_feedback(
    feedback: FeedbackRequest,
    db: Session = Depends(get_db),
    current_user: Optional[CurrentUser] = Depends(get_current_user),
):
    """Submit crowdsourced feedback on a report."""
    from backend.models.db import FeedbackDB, Report as ReportDB
    
    if feedback.report_id not in reports_store:
        db_report = db.query(ReportDB).filter(ReportDB.id == feedback.report_id).first()
        if not db_report:
            raise HTTPException(status_code=404, detail="Report not found")

    feedback_store.append(feedback.model_dump())

    try:
        user_uuid = uuid.UUID(current_user.id) if current_user else None
        db_feedback = FeedbackDB(
            report_id=feedback.report_id,
            user_id=user_uuid,
            feedback=f"Verdict: {feedback.user_verdict.value}. Comment: {feedback.comment or ''}",
        )
        db.add(db_feedback)
        db.commit()
    except Exception as e:
        logger.warning(f"Failed to persist feedback to DB: {e}")

    logger.info(f"Feedback received for report {feedback.report_id}: {feedback.user_verdict}")
    return {"status": "ok", "message": "Feedback recorded. Thank you!"}


@router.get("/dashboard")
async def get_user_dashboard(
    current_user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Retrieve personal dashboard stats for the authenticated user."""
    from backend.models.db import Report as ReportDB
    
    user_uuid = uuid.UUID(current_user.id)

    # Query Supabase/PostgreSQL for user scans
    total_scans = db.query(ReportDB).filter(ReportDB.user_id == user_uuid).count()
    fake_news = db.query(ReportDB).filter(
        ReportDB.user_id == user_uuid,
        ReportDB.verdict == "FALSE"
    ).count()

    deepfakes = db.query(ReportDB).filter(
        ReportDB.user_id == user_uuid,
        ReportDB.content_type == "image",
        ReportDB.verdict == "FALSE"
    ).count()

    voice_clones = db.query(ReportDB).filter(
        ReportDB.user_id == user_uuid,
        ReportDB.content_type == "audio",
        ReportDB.verdict == "FALSE"
    ).count()

    # Fetch recent scans
    recent_reports = db.query(ReportDB).filter(
        ReportDB.user_id == user_uuid
    ).order_by(ReportDB.created_at.desc()).limit(5).all()

    recent_scans = [
        {
            "id": r.id,
            "content_type": r.content_type,
            "text": (r.input_text or "")[:60] + "..." if r.input_text else "Media File/URL",
            "verdict": r.verdict,
            "confidence": int(r.confidence * 100),
            "date": r.created_at.strftime("%Y-%m-%d %H:%M"),
        }
        for r in recent_reports
    ]

    return {
        "total_scans": total_scans,
        "fake_news": fake_news,
        "deepfakes": deepfakes,
        "voice_clones": voice_clones,
        "recent_scans": recent_scans,
    }


@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: Session = Depends(get_db)):
    """Get aggregated dashboard statistics."""
    from backend.models.db import Report as ReportDB
    
    try:
        total_analyses = db.query(ReportDB).count()

        verdicts = {"TRUE": 0, "FALSE": 0, "MISLEADING": 0, "UNVERIFIED": 0}
        for v in verdicts.keys():
            verdicts[v] = db.query(ReportDB).filter(ReportDB.verdict == v).count()

        avg_trust = 50.0
        reports = db.query(ReportDB).all()
        if reports:
            avg_trust = sum(r.confidence for r in reports) / len(reports) * 100.0

        return StatsResponse(
            total_analyses=total_analyses,
            verdicts=verdicts,
            language_distribution={"en": total_analyses, "hi": 0, "ta": 0},
            top_flagged_domains=[],
            avg_trust_score=round(avg_trust, 1),
        )
    except Exception as e:
        logger.warning(f"Failed to fetch db stats, fallback to memory: {e}")
        return StatsResponse(
            total_analyses=0,
            verdicts={"TRUE": 0, "FALSE": 0, "MISLEADING": 0, "UNVERIFIED": 0},
            language_distribution={},
            top_flagged_domains=[],
            avg_trust_score=50.0,
        )


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0", "service": "TruthShield"}
