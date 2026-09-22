"""
TruthShield — API Routes
FastAPI REST endpoints for content analysis, reporting, and feedback.
"""

import logging
import os
import re
import secrets
import time
import uuid
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Depends, BackgroundTasks
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
from backend.api.auth import (
    get_current_user,
    require_user,
    require_user_or_api_key,
    get_current_user_or_api_key,
    CurrentUser
)
from backend.services.auth_service import AuthService
from backend.services.analysis_service import AnalysisService
from backend.services.analytics_service import AnalyticsService
from backend.services.notification_service import NotificationService
from backend.security import BlockedURLError, assert_url_is_public
import json

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()

# Verdict vocabulary emitted by ResultAggregator, grouped for reporting.
FALSE_VERDICTS = ("FALSE", "LIKELY FALSE", "MISLEADING")
TRUE_VERDICTS = ("TRUE", "VERIFIED", "LIKELY TRUE", "PARTIALLY TRUE")

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


# In-memory OTP store: {email: (code, issued_at, attempts)}.
# Single-process only — a multi-worker deployment needs this in Redis, since a
# code issued by one worker is invisible to the others.
otp_store: dict = {}
OTP_TTL_SECONDS = 600          # 10 minutes
OTP_MAX_ATTEMPTS = 5
OTP_STORE_MAX = 10_000


@router.post("/auth/otp")
async def send_otp(email_data: dict, db: Session = Depends(get_db)):
    """Send OTP to the user's email."""
    email = email_data.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    # Bound the store. It was an unbounded dict keyed by caller-supplied
    # address, so anyone could grow it without limit by POSTing new addresses.
    if len(otp_store) >= OTP_STORE_MAX:
        cutoff = time.time() - OTP_TTL_SECONDS
        for stale in [k for k, v in otp_store.items() if v[1] < cutoff]:
            otp_store.pop(stale, None)
        if len(otp_store) >= OTP_STORE_MAX:
            raise HTTPException(status_code=503, detail="Try again shortly")

    # secrets, not random: random is a Mersenne Twister seeded from system
    # entropy but fully predictable once enough outputs are observed, and
    # these codes are authentication material.
    otp = f"{secrets.randbelow(1_000_000):06d}"
    otp_store[email] = (otp, time.time(), 0)

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
        
    # There used to be a hardcoded fallback here: any request presenting the
    # literal OTP "123456" was accepted for any address, which minted a valid
    # session for an arbitrary account without ever seeing the real code. It
    # was labelled a dev convenience but ran unconditionally in every
    # environment. Removed outright — a backdoor that only the operator is
    # supposed to know about is still a backdoor.
    record = otp_store.get(email)
    if not record:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    expected_otp, issued_at, attempts = record

    if attempts >= OTP_MAX_ATTEMPTS:
        otp_store.pop(email, None)
        raise HTTPException(status_code=429, detail="Too many attempts. Request a new code.")

    if time.time() - issued_at > OTP_TTL_SECONDS:
        otp_store.pop(email, None)
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    # Constant-time: a plain != leaks how much of the code was right through
    # timing, which matters for a 6-digit secret.
    if not secrets.compare_digest(str(expected_otp), str(token)):
        otp_store[email] = (expected_otp, issued_at, attempts + 1)
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    # Single use.
    otp_store.pop(email, None)

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
    from datetime import datetime, timedelta, timezone
    
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
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


def hash_password(password: str) -> str:
    import hashlib
    import secrets
    salt = secrets.token_hex(16)
    hash_bytes = hashlib.pbkdf2_hmac(
        'sha256', 
        password.encode('utf-8'), 
        salt.encode('utf-8'), 
        100000
    )
    return f"pbkdf2_sha256$100000${salt}${hash_bytes.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    import hashlib
    import secrets
    if not hashed:
        return False
    try:
        parts = hashed.split('$')
        if len(parts) != 4 or parts[0] != 'pbkdf2_sha256':
            return False
        iterations = int(parts[1])
        salt = parts[2]
        original_hash = parts[3]
        
        new_hash_bytes = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            iterations
        )
        return secrets.compare_digest(new_hash_bytes.hex(), original_hash)
    except Exception:
        return False


@router.post("/auth/signup")
async def signup(payload: dict, db: Session = Depends(get_db)):
    """Register a new user with email and password."""
    email = payload.get("email")
    password = payload.get("password")
    
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")
        
    from backend.models.db import User
    # Check if user exists
    db_user = db.query(User).filter(User.email == email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    # Create new user
    hashed = hash_password(password)
    db_user = User(email=email, password_hash=hashed)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Generate JWT token
    from jose import jwt
    from datetime import datetime, timedelta, timezone
    
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
    token_payload = {
        "sub": str(db_user.id),
        "email": db_user.email,
        "exp": expire
    }
    access_token = jwt.encode(token_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(db_user.id),
            "email": db_user.email
        }
    }


@router.post("/auth/signin")
async def signin(payload: dict, db: Session = Depends(get_db)):
    """Authenticate a user with email and password."""
    email = payload.get("email")
    password = payload.get("password")
    
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")
        
    from backend.models.db import User
    db_user = db.query(User).filter(User.email == email).first()
    if not db_user or not db_user.password_hash:
        raise HTTPException(status_code=400, detail="Invalid email or password")
        
    if not verify_password(password, db_user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid email or password")
        
    # Generate JWT token
    from jose import jwt
    from datetime import datetime, timedelta, timezone
    
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
    token_payload = {
        "sub": str(db_user.id),
        "email": db_user.email,
        "exp": expire
    }
    access_token = jwt.encode(token_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(db_user.id),
            "email": db_user.email
        }
    }


@router.post("/auth/demo")
async def demo_login(db: Session = Depends(get_db)):
    """Demo Login — signs in as a guest/demo user."""
    demo_email = "demo@truthshield.ai"
    
    from backend.models.db import User
    db_user = db.query(User).filter(User.email == demo_email).first()
    if not db_user:
        db_user = User(email=demo_email)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
    # Generate JWT token
    from jose import jwt
    from datetime import datetime, timedelta, timezone
    
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
    token_payload = {
        "sub": str(db_user.id),
        "email": db_user.email,
        "exp": expire
    }
    access_token = jwt.encode(token_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(db_user.id),
            "email": db_user.email,
            "is_demo": True
        }
    }


@router.post("/auth/oauth-verify")
async def oauth_verify(payload: dict, db: Session = Depends(get_db)):
    """Verify Supabase OAuth session and return a local JWT token."""
    supabase_token = payload.get("supabase_token")

    # ── Identity comes from the verified token, never from the request body ──
    #
    # This endpoint previously trusted a caller-supplied `email` field and only
    # consulted the token when SUPABASE_JWT_SECRET happened to be configured —
    # which it is not by default. So an unauthenticated request of
    #
    #     POST /api/v1/auth/oauth-verify  {"email": "victim@example.com"}
    #
    # returned a valid session token for that account. Complete account
    # takeover for any address, with no credential of any kind.
    #
    # Two further holes in the verification path itself:
    #   * RS/ES/PS-signed tokens were decoded with verify_signature disabled,
    #     so a forged token was accepted as readily as a genuine one;
    #   * the email check was `if token_email and token_email != email`, so a
    #     token carrying no email claim satisfied it.
    if not settings.SUPABASE_JWT_SECRET:
        raise HTTPException(
            status_code=503,
            detail="OAuth sign-in is not configured on this server.",
        )
    if not supabase_token:
        raise HTTPException(status_code=401, detail="Missing session token")

    from jose import jwt as jose_jwt, JWTError

    try:
        header = jose_jwt.get_unverified_header(supabase_token)
        alg = header.get("alg", "HS256")

        # Only symmetric algorithms can be verified with a shared secret.
        # Asymmetric tokens need the provider's public keys, which this server
        # does not fetch — so they are refused rather than waved through.
        if not alg.startswith("HS"):
            logger.warning("Rejected Supabase token signed with unsupported alg %s", alg)
            raise HTTPException(
                status_code=401,
                detail="Unsupported token signature algorithm",
            )

        token_payload = jose_jwt.decode(
            supabase_token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256", "HS384", "HS512"],
            options={"verify_aud": False},
        )
    except HTTPException:
        raise
    except JWTError:
        # The underlying reason is logged, not returned: the exception text
        # describes our verification setup and is of use only to an attacker.
        logger.warning("Supabase token verification failed", exc_info=True)
        raise HTTPException(status_code=401, detail="Invalid session token")

    email = token_payload.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Session token carries no email")

    # Auto-create user in database if they don't exist
    from backend.models.db import User
    db_user = db.query(User).filter(User.email == email).first()
    if not db_user:
        db_user = User(email=email)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
    # Generate local JWT token
    from jose import jwt as jose_jwt
    from datetime import datetime, timedelta, timezone
    
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
    token_payload = {
        "sub": str(db_user.id),
        "email": db_user.email,
        "exp": expire
    }
    access_token = jose_jwt.encode(token_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(db_user.id),
            "email": db_user.email
        }
    }


def run_async_analysis_in_background(
    report_id: str,
    text: Optional[str],
    file_path: Optional[str],
    url: Optional[str],
    content_type: ContentType,
    lang: str,
    user_id: Optional[str] = None,
    org_id: Optional[str] = None
):
    """FastAPI BackgroundTasks fallback to execute decision pipeline."""
    import asyncio
    from backend.pipeline.decision_pipeline import DecisionPipeline
    from backend.models.db import SessionLocal, Report as ReportDB, EvidenceDB
    
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    pipeline = DecisionPipeline()
    report = loop.run_until_complete(
        pipeline.execute(
            text=text,
            file_path=file_path,
            url=url,
            content_type=content_type,
            lang=lang
        )
    )
    
    db = SessionLocal()
    try:
        import json
        db_report = db.query(ReportDB).filter(ReportDB.id == report_id).first()
        if db_report:
            db_report.verdict = report.credibility.verdict
            db_report.confidence = report.credibility.trust_score / 100.0
            if user_id:
                db_report.user_id = uuid.UUID(user_id)
            if org_id and org_id != "personal":
                db_report.org_id = uuid.UUID(org_id)
            
            # Serialized JSON fields
            db_report.claims_json = json.dumps([cv.model_dump() for cv in report.claims]) if report.claims else None
            db_report.explanation_json = json.dumps(report.explanation.model_dump()) if report.explanation else None
            db_report.counter_narrative_json = json.dumps(report.counter_narrative.model_dump()) if report.counter_narrative else None
            db_report.inconsistencies_json = json.dumps([inc.model_dump() for inc in report.inconsistencies]) if report.inconsistencies else None
            db_report.social_signals_json = json.dumps([sig.model_dump() for sig in report.social_signals]) if report.social_signals else None
            db_report.risk_factors_json = json.dumps(report.risk_factors) if report.risk_factors else None
            db_report.signal_correlations_json = json.dumps(report.signal_correlations) if report.signal_correlations else None
            db_report.confidence_profile_json = json.dumps(report.confidence_profile) if report.confidence_profile else None
            db_report.verdict_reasons_json = json.dumps(report.verdict_reasons) if report.verdict_reasons else None
            db_report.processing_time_seconds = report.processing_time_seconds or 0.0

            # Save evidence
            if report.claims:
                for claim_verdict in report.claims:
                    for ev in claim_verdict.evidence:
                        db_ev = EvidenceDB(
                            report_id=report_id,
                            source_url=ev.url,
                            source_name=ev.title,
                            credibility_score=ev.source_score,
                        )
                        db.add(db_ev)
            db.commit()

            # Log audit trail if org_id is provided
            if org_id and org_id != "personal":
                AuthService.log_action(
                    db,
                    uuid.UUID(org_id),
                    uuid.UUID(user_id) if user_id else None,
                    "analyze_created",
                    {"report_id": report_id, "verdict": report.credibility.verdict, "content_type": content_type.value}
                )
    except Exception as e:
        logger.error(f"Failed to save background analysis results: {e}")
    finally:
        db.close()


@router.post("/analyze", response_model=AnalysisReport)
async def analyze_content(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    lang: str = Form("en"),
    async_mode: bool = Form(False),
    org_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_user_or_api_key),
):
    """
    Analyze content for misinformation.
    Supports asynchronous processing for large media uploads (video/audio).
    Accepts user bearer token (JWT) or custom X-API-Key header.
    """
    settings = get_settings()
    from backend.models.schemas import Language

    # Resolve Form default parameters if called directly in tests
    resolved_lang = lang.default if hasattr(lang, "default") else lang
    resolved_async_mode = async_mode.default if hasattr(async_mode, "default") else async_mode
    resolved_org_id_param = org_id.default if hasattr(org_id, "default") else org_id
    resolved_url = url.default if hasattr(url, "default") else url
    resolved_text = text.default if hasattr(text, "default") else text

    content_type = ContentType.TEXT
    file_path = None

    if file and hasattr(file, "filename") and file.filename:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            content_type = ContentType.IMAGE
        elif ext in (".mp3", ".wav", ".ogg", ".m4a", ".flac"):
            content_type = ContentType.AUDIO
        elif ext in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
            content_type = ContentType.VIDEO
        else:
            content_type = ContentType.TEXT

        # The extension is taken from the caller's filename, so constrain it to
        # a known-safe set rather than interpolating it into a path. The stem
        # is a fresh uuid4, so the caller never controls the filename itself.
        if ext and not re.fullmatch(r"\.[A-Za-z0-9]{1,8}", ext):
            raise HTTPException(status_code=400, detail="Unsupported file type")

        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        file_path = str(settings.UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}")

        # Streamed with a running size check. `await file.read()` pulled the
        # whole upload into memory before anything looked at its size, so a
        # single large POST could exhaust the process — MAX_UPLOAD_SIZE_MB was
        # defined in config but never actually consulted anywhere.
        max_bytes = settings.max_upload_bytes
        written = 0
        try:
            with open(file_path, "wb") as f:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > max_bytes:
                        raise HTTPException(
                            status_code=413,
                            detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB limit",
                        )
                    f.write(chunk)
        except HTTPException:
            # Don't leave the partial upload behind.
            try:
                os.remove(file_path)
            except OSError:
                pass
            raise

        content = b""
        if content_type == ContentType.TEXT:
            with open(file_path, "rb") as f:
                content = f.read()

        if content_type == ContentType.TEXT:
            # Try PDF extraction for .pdf files
            if ext == ".pdf":
                try:
                    from PyPDF2 import PdfReader
                    reader = PdfReader(file_path)
                    pages_text = []
                    for page in reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            pages_text.append(page_text)
                    if pages_text:
                        resolved_text = "\n".join(pages_text)
                        logger.info(f"PDF extracted: {len(pages_text)} pages, {len(resolved_text)} chars")
                    else:
                        resolved_text = content.decode("utf-8", errors="ignore")
                except ImportError:
                    logger.warning("PyPDF2 not installed, falling back to raw text decode for PDF")
                    resolved_text = content.decode("utf-8", errors="ignore")
                except Exception as e:
                    logger.warning(f"PDF extraction failed: {e}, falling back to raw decode")
                    resolved_text = content.decode("utf-8", errors="ignore")
            else:
                resolved_text = content.decode("utf-8", errors="ignore")

    elif resolved_url:
        # Reject unfetchable targets here rather than letting the scraper
        # return an empty page: /analyze echoes the fetched body back to the
        # caller, so this URL is the entry point for server-side request
        # forgery and the refusal belongs at the boundary.
        try:
            resolved_url = assert_url_is_public(resolved_url)
        except BlockedURLError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        content_type = ContentType.URL
    elif resolved_text:
        content_type = ContentType.TEXT
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one of: file, url, or text",
        )

    # Determine user/organization ownership
    user_uuid = uuid.UUID(current_user.id)
    resolved_org_id = None
    if current_user.org_id and current_user.org_id != "personal":
        resolved_org_id = uuid.UUID(current_user.org_id)
    elif resolved_org_id_param and resolved_org_id_param != "personal":
        role = AuthService.check_user_role(db, uuid.UUID(resolved_org_id_param), user_uuid)
        if not role:
            raise HTTPException(status_code=403, detail="You are not a member of this workspace")
        resolved_org_id = uuid.UUID(resolved_org_id_param)

    # Automatically queue background job for large/heavy contents
    should_queue = resolved_async_mode or content_type in (ContentType.VIDEO, ContentType.AUDIO)

    if should_queue:
        report_id = uuid.uuid4().hex
        from backend.models.db import Report as ReportDB
        db_report = ReportDB(
            id=report_id,
            user_id=user_uuid,
            org_id=resolved_org_id,
            content_type=content_type.value,
            input_text=resolved_text or resolved_url or (file.filename if file else "Media File"),
            verdict="UNVERIFIED",
            confidence=0.0,
        )
        db.add(db_report)
        db.commit()

        celery_queued = False
        try:
            # Queue Celery job via Redis broker
            from backend.tasks import analyze_content_task
            analyze_content_task.delay(
                report_id=report_id,
                text=resolved_text,
                file_path=file_path,
                url=resolved_url,
                content_type=content_type.value,
                lang=resolved_lang,
                user_id=str(user_uuid),
                org_id=str(resolved_org_id) if resolved_org_id else None
            )
            celery_queued = True
            logger.info(f"Asynchronously queued report {report_id} to Celery worker.")
        except Exception as e:
            logger.warning(f"Failed to queue to Celery: {e}. Falling back to FastAPI BackgroundTasks.")

        if not celery_queued:
            background_tasks.add_task(
                run_async_analysis_in_background,
                report_id=report_id,
                text=resolved_text,
                file_path=file_path,
                url=resolved_url,
                content_type=content_type,
                lang=resolved_lang,
                user_id=str(user_uuid),
                org_id=str(resolved_org_id) if resolved_org_id else None
            )
            logger.info(f"Asynchronously queued report {report_id} to FastAPI BackgroundTasks.")

        from backend.models.schemas import CredibilityScore
        return AnalysisReport(
            id=report_id,
            content_type=content_type,
            original_text=resolved_text or resolved_url or (file.filename if file else "Media File"),
            language=Language(resolved_lang),
            credibility=CredibilityScore(
                trust_score=0,
                verdict="UNVERIFIED",
                confidence_band="LOW"
            ),
            processing_time_seconds=0.0,
            risk_factors=["Processing in background queue"]
        )

    # Process synchronously using AnalysisService
    report = await AnalysisService.analyze(
        db=db,
        text=resolved_text,
        file_path=file_path,
        url=resolved_url,
        content_type=content_type,
        lang=resolved_lang,
        user_id=user_uuid,
        org_id=resolved_org_id
    )

    return report


@router.get("/report/{report_id}", response_model=AnalysisReport)
async def get_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[CurrentUser] = Depends(get_current_user),
):
    """
    Retrieve a full analysis report by ID.

    A report that belongs to a user is only served to that user, or to a member
    of the workspace it was filed under. This endpoint previously took no
    identity at all: the 128-bit id made reports impractical to enumerate, but
    anyone who came by an id — a shared link, a proxy log, a browser history —
    could read another workspace's analysis in full, including the submitted
    content. Reports with no owner (anonymous submissions) stay public so
    existing share links keep working.
    """
    report = reports_store.get(report_id)
    if not report:
        from backend.models.db import Report as ReportDB
        db_report = db.query(ReportDB).filter(ReportDB.id == report_id).first()
        if not db_report:
            raise HTTPException(status_code=404, detail="Report not found")

        if db_report.user_id is not None:
            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required")

            caller_id = uuid.UUID(current_user.id)
            allowed = db_report.user_id == caller_id
            if not allowed and db_report.org_id is not None:
                allowed = bool(AuthService.check_user_role(db, db_report.org_id, caller_id))
            if not allowed:
                # 404 rather than 403: confirming the id exists tells an
                # unauthorised caller something they should not learn.
                raise HTTPException(status_code=404, detail="Report not found")
        
        # Reconstruct AnalysisReport from db_report JSON fields
        import json
        from backend.models.schemas import (
            CredibilityScore, Evidence, ClaimVerdict, Explanation,
            CounterNarrative, Inconsistency, SocialSignal, Language
        )
        
        claims = []
        if db_report.claims_json:
            try:
                claims_data = json.loads(db_report.claims_json)
                claims = [ClaimVerdict(**c) for c in claims_data]
            except Exception as e:
                logger.warning(f"Failed to deserialize claims: {e}")
                
        explanation = None
        if db_report.explanation_json:
            try:
                explanation = Explanation(**json.loads(db_report.explanation_json))
            except Exception as e:
                logger.warning(f"Failed to deserialize explanation: {e}")
                
        counter_narrative = None
        if db_report.counter_narrative_json:
            try:
                counter_narrative = CounterNarrative(**json.loads(db_report.counter_narrative_json))
            except Exception as e:
                logger.warning(f"Failed to deserialize counter_narrative: {e}")
                
        inconsistencies = []
        if db_report.inconsistencies_json:
            try:
                inconsistencies = [Inconsistency(**inc) for inc in json.loads(db_report.inconsistencies_json)]
            except Exception as e:
                logger.warning(f"Failed to deserialize inconsistencies: {e}")
                
        social_signals = []
        if db_report.social_signals_json:
            try:
                social_signals = [SocialSignal(**sig) for sig in json.loads(db_report.social_signals_json)]
            except Exception as e:
                logger.warning(f"Failed to deserialize social_signals: {e}")
                
        risk_factors = []
        if db_report.risk_factors_json:
            try:
                risk_factors = json.loads(db_report.risk_factors_json)
            except Exception as e:
                logger.warning(f"Failed to deserialize risk_factors: {e}")
                
        signal_correlations = {}
        if db_report.signal_correlations_json:
            try:
                signal_correlations = json.loads(db_report.signal_correlations_json)
            except Exception as e:
                logger.warning(f"Failed to deserialize signal_correlations: {e}")
                
        confidence_profile = None
        if db_report.confidence_profile_json:
            try:
                confidence_profile = json.loads(db_report.confidence_profile_json)
            except Exception as e:
                logger.warning(f"Failed to deserialize confidence_profile: {e}")

        verdict_reasons = []
        if hasattr(db_report, "verdict_reasons_json") and db_report.verdict_reasons_json:
            try:
                verdict_reasons = json.loads(db_report.verdict_reasons_json)
            except Exception as e:
                logger.warning(f"Failed to deserialize verdict_reasons: {e}")

        # Fallback for old records: reconstruct a claim if none exist in claims_json but there is evidence in the DB
        if not claims and db_report.evidence:
            from backend.models.schemas import Claim
            evidence_list = [
                Evidence(
                    title=ev.source_name or "",
                    url=ev.source_url,
                    snippet="",
                    source_score=ev.credibility_score,
                )
                for ev in db_report.evidence
            ]
            claims = [
                ClaimVerdict(
                    claim=Claim(text=db_report.input_text or "Ingested URL/Media"),
                    verdict=db_report.verdict,
                    confidence=db_report.confidence,
                    evidence=evidence_list,
                )
            ]
        
        report = AnalysisReport(
            id=db_report.id,
            content_type=ContentType(db_report.content_type),
            original_text=db_report.input_text,
            language=Language(db_report.language) if db_report.language else Language.EN,
            credibility=CredibilityScore(
                trust_score=int(db_report.confidence * 100),
                verdict=db_report.verdict,
            ),
            claims=claims,
            explanation=explanation,
            counter_narrative=counter_narrative,
            inconsistencies=inconsistencies,
            social_signals=social_signals,
            risk_factors=risk_factors,
            signal_correlations=signal_correlations,
            confidence_profile=confidence_profile,
            verdict_reasons=verdict_reasons,
            processing_time_seconds=db_report.processing_time_seconds or 0.0,
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
    org_id: Optional[str] = None,
    current_user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Retrieve personal or workspace-scoped dashboard stats for the authenticated user."""
    if org_id and org_id != "personal":
        role = AuthService.check_user_role(db, uuid.UUID(org_id), uuid.UUID(current_user.id))
        if not role:
            raise HTTPException(status_code=403, detail="You are not a member of this workspace")
        return AnalyticsService.get_workspace_stats(db, uuid.UUID(org_id))

    from backend.models.db import Report as ReportDB
    from sqlalchemy import case, func

    user_uuid = uuid.UUID(current_user.id)

    # All four headline tiles in one pass over the user's reports.
    # The aggregator emits graded verdicts ("LIKELY FALSE", "MISLEADING"), so
    # matching only the exact string "FALSE" under-counted nearly every threat.
    is_false = ReportDB.verdict.in_(FALSE_VERDICTS)
    totals = db.query(
        func.count(ReportDB.id),
        func.sum(case((is_false, 1), else_=0)),
        func.sum(case(((is_false) & (ReportDB.content_type == "image"), 1), else_=0)),
        func.sum(case(((is_false) & (ReportDB.content_type == "audio"), 1), else_=0)),
    ).filter(ReportDB.user_id == user_uuid).one()
    total_scans = totals[0] or 0
    fake_news = totals[1] or 0
    deepfakes = totals[2] or 0
    voice_clones = totals[3] or 0

    # Weekly scan trend — one grouped query rather than a COUNT per day.
    from datetime import datetime, timedelta, timezone
    today = datetime.now(timezone.utc).date()
    week_start = datetime.combine(today - timedelta(days=6), datetime.min.time())

    per_day = dict(
        db.query(func.date(ReportDB.created_at), func.count(ReportDB.id))
        .filter(ReportDB.user_id == user_uuid, ReportDB.created_at >= week_start)
        .group_by(func.date(ReportDB.created_at))
        .all()
    )

    weekly_trend = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        # SQLite returns date() as a string; PostgreSQL returns a date object.
        count = per_day.get(d) or per_day.get(d.isoformat()) or 0
        weekly_trend.append({"day": d.strftime("%a"), "scans": count})

    # Fetch recent scans
    recent_reports = db.query(ReportDB).filter(
        ReportDB.user_id == user_uuid
    ).order_by(ReportDB.created_at.desc()).limit(10).all()

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
        "weekly_trend": weekly_trend,
        "recent_scans": recent_scans,
    }


# ── Workspace / Organization Endpoints ───

@router.post("/organizations")
async def create_organization(
    data: dict,
    current_user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db)
):
    name = data.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="Workspace name is required")
    org = AuthService.create_organization(db, name, uuid.UUID(current_user.id))
    return {"id": str(org.id), "name": org.name}


@router.get("/organizations")
async def list_organizations(
    current_user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db)
):
    from backend.models.db import OrganizationMember, Organization
    memberships = db.query(OrganizationMember).filter(OrganizationMember.user_id == uuid.UUID(current_user.id)).all()
    orgs = []
    for m in memberships:
        org = db.query(Organization).filter(Organization.id == m.org_id).first()
        if org:
            orgs.append({
                "id": str(org.id),
                "name": org.name,
                "role": m.role
            })
    return orgs


@router.post("/organizations/{org_id}/invite")
async def invite_member(
    org_id: str,
    data: dict,
    current_user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db)
):
    email = data.get("email")
    role = data.get("role", "Member")
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    
    if org_id == "personal":
        raise HTTPException(status_code=400, detail="Cannot invite members to personal node.")
        
    actor_role = AuthService.check_user_role(db, uuid.UUID(org_id), uuid.UUID(current_user.id))
    if actor_role != "Admin":
        raise HTTPException(status_code=403, detail="Only Admins can invite team members.")
        
    member = AuthService.invite_member(
        db,
        uuid.UUID(org_id),
        email,
        role,
        uuid.UUID(current_user.id)
    )
    return {"status": "ok", "message": f"Successfully invited {email} as {role}."}


@router.get("/organizations/{org_id}/members")
async def list_members(
    org_id: str,
    current_user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db)
):
    if org_id == "personal":
        from datetime import datetime, timezone
        return [
            {
                "id": str(current_user.id),
                "email": current_user.email,
                "role": "Owner",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        ]
        
    role = AuthService.check_user_role(db, uuid.UUID(org_id), uuid.UUID(current_user.id))
    if not role:
        raise HTTPException(status_code=403, detail="You are not a member of this workspace.")
        
    members_data = AuthService.get_members(db, uuid.UUID(org_id))
    return [
        {
            "id": str(m.id),
            "email": email,
            "role": m.role,
            "created_at": m.created_at.isoformat()
        }
        for m, email in members_data
    ]


@router.post("/organizations/{org_id}/apikeys")
async def create_api_key(
    org_id: str,
    data: dict,
    current_user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db)
):
    if org_id == "personal":
        raise HTTPException(status_code=400, detail="Cannot create API keys for personal node.")
        
    label = data.get("label", "Production API Key")
    role = AuthService.check_user_role(db, uuid.UUID(org_id), uuid.UUID(current_user.id))
    if role != "Admin":
        raise HTTPException(status_code=403, detail="Only Admins can generate API Keys.")
        
    key_record, raw_key = AuthService.generate_api_key(
        db,
        uuid.UUID(org_id),
        label,
        uuid.UUID(current_user.id)
    )
    return {
        "id": str(key_record.id),
        "label": key_record.label,
        "api_key": raw_key,
        "created_at": key_record.created_at.isoformat()
    }


@router.get("/organizations/{org_id}/apikeys")
async def list_api_keys(
    org_id: str,
    current_user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db)
):
    if org_id == "personal":
        return []
        
    role = AuthService.check_user_role(db, uuid.UUID(org_id), uuid.UUID(current_user.id))
    if not role:
        raise HTTPException(status_code=403, detail="You are not a member of this workspace.")
        
    keys = AuthService.list_api_keys(db, uuid.UUID(org_id))
    return [
        {
            "id": str(k.id),
            "label": k.label,
            "is_active": k.is_active,
            "created_at": k.created_at.isoformat()
        }
        for k in keys
    ]


@router.delete("/apikeys/{key_id}")
async def revoke_api_key(
    key_id: str,
    current_user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db)
):
    from backend.models.db import APIKey
    key_record = db.query(APIKey).filter(APIKey.id == uuid.UUID(key_id)).first()
    if not key_record:
        raise HTTPException(status_code=404, detail="API Key not found")
        
    role = AuthService.check_user_role(db, key_record.org_id, uuid.UUID(current_user.id))
    if role != "Admin":
        raise HTTPException(status_code=403, detail="Only Admins can revoke API Keys.")
        
    success = AuthService.revoke_api_key(db, uuid.UUID(key_id), uuid.UUID(current_user.id))
    return {"status": "ok" if success else "failed"}


@router.get("/organizations/{org_id}/audit-logs")
async def get_audit_logs(
    org_id: str,
    current_user: CurrentUser = Depends(require_user),
    db: Session = Depends(get_db)
):
    if org_id == "personal":
        return []
        
    role = AuthService.check_user_role(db, uuid.UUID(org_id), uuid.UUID(current_user.id))
    if not role:
        raise HTTPException(status_code=403, detail="You are not a member of this workspace.")
        
    logs = AuthService.get_audit_logs(db, uuid.UUID(org_id))
    return [
        {
            "id": str(l.id),
            "user_email": email or "System",
            "action": l.action,
            "details": json.loads(l.details) if l.details else {},
            "created_at": l.created_at.isoformat()
        }
        for l, email in logs
    ]


# ── Threat Intelligence Telemetry Endpoints ───

@router.get("/realtime/threats")
async def get_realtime_threats(
    db: Session = Depends(get_db)
):
    return AnalyticsService.get_threat_vectors(db)


@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: Session = Depends(get_db)):
    """Get aggregated dashboard statistics."""
    from backend.models.db import Report as ReportDB
    
    from sqlalchemy import func

    try:
        # Single grouped query instead of one COUNT per verdict, with the
        # aggregator's graded verdicts folded into the four reported buckets.
        verdicts = {"TRUE": 0, "FALSE": 0, "MISLEADING": 0, "UNVERIFIED": 0}
        total_analyses = 0
        for verdict, count in db.query(ReportDB.verdict, func.count(ReportDB.id)).group_by(ReportDB.verdict):
            total_analyses += count
            if verdict == "MISLEADING":
                verdicts["MISLEADING"] += count
            elif verdict in FALSE_VERDICTS:
                verdicts["FALSE"] += count
            elif verdict in TRUE_VERDICTS:
                verdicts["TRUE"] += count
            else:
                verdicts["UNVERIFIED"] += count

        # Average in SQL — loading every report to average one column made this
        # endpoint scale linearly with table size.
        avg_confidence = db.query(func.avg(ReportDB.confidence)).scalar()
        avg_trust = float(avg_confidence) * 100.0 if avg_confidence is not None else 50.0

        # Compute actual language distribution from DB
        lang_dist = {}
        lang_counts = db.query(ReportDB.language, func.count(ReportDB.id)).group_by(ReportDB.language).all()
        for lang_code, count in lang_counts:
            if lang_code:
                lang_dist[lang_code] = count
        # Ensure all supported languages are present
        for code in ("en", "hi", "ta"):
            lang_dist.setdefault(code, 0)

        return StatsResponse(
            total_analyses=total_analyses,
            verdicts=verdicts,
            language_distribution=lang_dist,
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


@router.get("/realtime/trending")
async def get_trending_misinfo(db: Session = Depends(get_db)):
    """Retrieve currently active and flagged trending misinformation from social feeds."""
    from backend.models.db import TrendingMisinfo
    items = db.query(TrendingMisinfo).order_by(TrendingMisinfo.virality_score.desc()).limit(10).all()
    return [
        {
            "id": str(item.id),
            "claim": item.claim,
            "verdict": item.verdict,
            "confidence": int(item.confidence * 100),
            "platform": item.source_platform,
            "virality": item.virality_score,
            "created_at": item.created_at.isoformat()
        }
        for item in items
    ]


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0", "service": "TruthShield"}
