"""HTTP routes. Thin — orchestration lives in `truthshield.services`."""

from __future__ import annotations

import logging
import os
import re
import uuid
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status,
)
from sqlalchemy import func
from sqlalchemy.orm import Session

from truthshield.api import schemas
from truthshield.api.deps import current_principal, require_principal
from truthshield.domain.types import ContentType, Language
from truthshield.infra.database import get_session
from truthshield.infra.models import Feedback, Report
from truthshield.services import auth
from truthshield.services.analysis import AnalysisService
from truthshield.services.auth import Principal
from truthshield.settings import get_settings

logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="/auth", tags=["auth"])
analysis_router = APIRouter(tags=["analysis"])
meta_router = APIRouter(tags=["meta"])


# ══════════════════════════════════════════════════════════════
# Auth
# ══════════════════════════════════════════════════════════════

@auth_router.post("/signup", response_model=schemas.TokenResponse, status_code=201)
def signup(payload: schemas.SignupRequest, session: Session = Depends(get_session)):
    email = payload.email.lower()
    if session.query(auth.User).filter(auth.User.email == email).first():
        # Same message and status as a weak password would give, so this
        # endpoint cannot be used to discover which addresses are registered.
        raise HTTPException(status_code=400, detail="Could not create this account.")

    user = auth.User(email=email, password_hash=auth.hash_password(payload.password))
    session.add(user)
    session.commit()
    session.refresh(user)

    org = auth.ensure_personal_org(session, user)
    token, expires = auth.issue_token(user, org.id)
    return schemas.TokenResponse(
        access_token=token, expires_in=expires,
        user=schemas.UserSummary(id=str(user.id), email=user.email, org_id=str(org.id)),
    )


@auth_router.post("/signin", response_model=schemas.TokenResponse)
def signin(payload: schemas.SigninRequest, session: Session = Depends(get_session)):
    user = session.query(auth.User).filter(auth.User.email == payload.email.lower()).first()

    # verify_password runs the full derivation even with no stored hash, so a
    # missing account and a wrong password take the same time.
    if not auth.verify_password(payload.password, user.password_hash if user else None):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is disabled.")

    org = auth.ensure_personal_org(session, user)
    token, expires = auth.issue_token(user, org.id)
    return schemas.TokenResponse(
        access_token=token, expires_in=expires,
        user=schemas.UserSummary(id=str(user.id), email=user.email, org_id=str(org.id)),
    )


@auth_router.post("/otp")
def request_otp(payload: schemas.OTPRequest):
    """
    Send a login code.

    Always reports success: telling the caller whether an address is
    registered turns this into an account-enumeration oracle.
    """
    code = auth.OTPStore().issue(payload.email.lower())
    settings = get_settings()
    if settings.APP_ENV.is_development:
        logger.info("OTP for %s: %s", payload.email, code)
    else:
        # A real deployment sends this by email; it must never be logged.
        logger.info("OTP issued for %s", payload.email)
    return {"status": "sent"}


@auth_router.post("/otp/verify", response_model=schemas.TokenResponse)
def verify_otp(payload: schemas.OTPVerifyRequest, session: Session = Depends(get_session)):
    if not auth.OTPStore().verify(payload.email.lower(), payload.code):
        raise HTTPException(status_code=400, detail="Invalid or expired code.")

    user = auth.ensure_user(session, payload.email.lower())
    org = auth.ensure_personal_org(session, user)
    token, expires = auth.issue_token(user, org.id)
    return schemas.TokenResponse(
        access_token=token, expires_in=expires,
        user=schemas.UserSummary(id=str(user.id), email=user.email, org_id=str(org.id)),
    )


@auth_router.get("/me", response_model=schemas.UserSummary)
def me(principal: Principal = Depends(require_principal)):
    return schemas.UserSummary(
        id=str(principal.user_id), email=principal.email,
        org_id=str(principal.org_id) if principal.org_id else None,
    )


# ══════════════════════════════════════════════════════════════
# Analysis
# ══════════════════════════════════════════════════════════════

_SAFE_EXT = re.compile(r"^\.[A-Za-z0-9]{1,8}$")


@analysis_router.post("/analyze", response_model=None, status_code=200)
async def analyze(
    request: Request,
    text: Optional[str] = Form(None),
    url: Optional[str] = Form(None),
    language: str = Form("en"),
    async_mode: bool = Form(False),
    file: Optional[UploadFile] = File(None),
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
):
    settings = get_settings()
    service = AnalysisService(session)

    content_type = ContentType.TEXT
    file_path: Optional[str] = None

    if file and file.filename:
        from truthshield.services.ingest import classify_extension

        # The stored name is a fresh uuid4, so a crafted filename cannot
        # escape the upload directory. Path separators are still refused
        # outright: nothing legitimate sends them, and accepting them silently
        # would leave the next person to touch this code reasoning about
        # traversal rather than reading a flat rejection.
        if any(sep in file.filename for sep in ("/", "\\", "\x00")) or ".." in file.filename:
            raise HTTPException(status_code=400, detail="Invalid file name.")

        content_type = classify_extension(file.filename)

        ext = os.path.splitext(file.filename)[1].lower()
        if ext and not _SAFE_EXT.match(ext):
            raise HTTPException(status_code=400, detail="Unsupported file type.")

        # Streamed with a running cap. Reading the whole upload first, as the
        # previous version did, let one request exhaust process memory.
        file_path = str(settings.UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}")
        written = 0
        try:
            with open(file_path, "wb") as out:
                while chunk := await file.read(1024 * 1024):
                    written += len(chunk)
                    if written > settings.max_upload_bytes:
                        raise HTTPException(
                            status_code=413,
                            detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB limit.",
                        )
                    out.write(chunk)
        except HTTPException:
            _remove(file_path)
            raise
    elif url:
        from truthshield.security import BlockedURLError, assert_url_is_public
        try:
            url = assert_url_is_public(url)
        except BlockedURLError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        content_type = ContentType.URL
    elif not text or not text.strip():
        raise HTTPException(status_code=400, detail="Provide text, a URL, or a file.")

    if text and len(text) > settings.MAX_TEXT_LENGTH:
        raise HTTPException(
            status_code=413,
            detail=f"Text exceeds the {settings.MAX_TEXT_LENGTH} character limit.",
        )

    try:
        lang = Language(language)
    except ValueError:
        lang = Language.EN

    if async_mode or content_type in (ContentType.VIDEO, ContentType.AUDIO):
        report_id = service.enqueue(
            text=text, url=url, file_path=file_path,
            content_type=content_type, language=lang, principal=principal,
        )
        return schemas.QueuedResponse(
            id=report_id, poll_url=f"/api/v1/reports/{report_id}"
        )

    report = await service.analyze(
        report_id=uuid.uuid4().hex,
        text=text, url=url, file_path=file_path,
        content_type=content_type.value, language=lang.value,
        user_id=str(principal.user_id),
        org_id=str(principal.org_id) if principal.org_id else None,
    )
    return schemas.ReportOut.of(report)


@analysis_router.get("/reports/{report_id}", response_model=schemas.ReportOut)
def get_report(
    report_id: str,
    principal: Optional[Principal] = Depends(current_principal),
    session: Session = Depends(get_session),
):
    row = session.get(Report, report_id)
    if not row:
        raise HTTPException(status_code=404, detail="Report not found.")

    if not auth.can_read_report(session, row, principal):
        # 404, not 403: confirming the id exists tells an unauthorised caller
        # something they should not learn.
        raise HTTPException(status_code=404, detail="Report not found.")

    if row.status in ("queued", "running"):
        return schemas.ReportOut.of(
            AnalysisService.placeholder(row), status=row.status
        )
    if row.status == "failed":
        raise HTTPException(status_code=422, detail=row.error or "Analysis failed.")

    return schemas.ReportOut.of(AnalysisService.rehydrate(row), status=row.status)


@analysis_router.get("/reports", response_model=List[schemas.ReportSummary])
def list_reports(
    limit: int = 20,
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
):
    limit = max(1, min(limit, 100))
    rows = (
        session.query(Report)
        .filter(Report.user_id == principal.user_id)
        .order_by(Report.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        schemas.ReportSummary(
            id=r.id, status=r.status, verdict=r.verdict, trust_score=r.trust_score,
            content_type=r.content_type,
            excerpt=(r.input_text or r.source_url or "")[:160] or None,
            created_at=r.created_at,
        )
        for r in rows
    ]


@analysis_router.post("/feedback", status_code=201)
def submit_feedback(
    payload: schemas.FeedbackRequest,
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
):
    row = session.get(Report, payload.report_id)
    if not row or not auth.can_read_report(session, row, principal):
        raise HTTPException(status_code=404, detail="Report not found.")

    session.add(Feedback(
        report_id=row.id, user_id=principal.user_id,
        user_verdict=payload.user_verdict.value, comment=payload.comment,
    ))
    session.commit()
    return {"status": "recorded"}


# ══════════════════════════════════════════════════════════════
# Meta
# ══════════════════════════════════════════════════════════════

@meta_router.get("/stats", response_model=schemas.StatsResponse)
def stats(session: Session = Depends(get_session)):
    rows = (
        session.query(Report.verdict, func.count(Report.id))
        .filter(Report.status == "complete")
        .group_by(Report.verdict)
        .all()
    )
    verdicts = {verdict: count for verdict, count in rows}
    total = sum(verdicts.values())

    avg = session.query(func.avg(Report.trust_score)).filter(
        Report.status == "complete"
    ).scalar()

    langs = dict(
        session.query(Report.language, func.count(Report.id))
        .group_by(Report.language).all()
    )

    return schemas.StatsResponse(
        total_analyses=total,
        verdicts=verdicts,
        average_trust_score=round(float(avg), 1) if avg is not None else 0.0,
        languages=langs,
    )


@meta_router.get("/health", response_model=schemas.HealthResponse)
def health():
    """
    Liveness plus an honest capability report.

    `capabilities` says which detectors can actually run. An operator should
    be able to see that OCR is missing here, rather than inferring it from
    suspiciously clean results.
    """
    from truthshield.detectors.registry import availability
    from truthshield.infra.cache import get_cache
    from truthshield.infra.celery_app import broker_reachable
    from truthshield.infra.database import check_connection

    db_ok = check_connection()
    return schemas.HealthResponse(
        status="ok" if db_ok else "degraded",
        version="2.0.0",
        database=db_ok,
        cache=get_cache().health(),
        broker=broker_reachable(),
        capabilities=availability(),
    )


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
