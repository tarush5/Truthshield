"""
2.0 HTTP surface: investigations, synchronous analysis, platform, admin.

Handlers are plain `def` on purpose: FastAPI runs them in its thread pool,
where the pipeline may start its own event loop for evidence retrieval. An
`async def` handler would run on the server's loop and block it for the
length of an analysis.
"""


import csv
import io
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from truthshield.api.deps import require_principal, require_role
from truthshield.api.errors import ApiError
from truthshield.api.limits import expensive_limit
from truthshield.infra.database import get_session
from truthshield.infra.models import AuditLog, User
from truthshield.investigations import demo, service
from truthshield.investigations.service import InvestigationError
from truthshield.services.audit import record as record_audit
from truthshield.services.auth import Principal

investigations_router = APIRouter(prefix="/investigations", tags=["investigations"])
analyze_v2_router = APIRouter(prefix="/analyze", tags=["analysis (2.0)"])
platform_router = APIRouter(tags=["platform"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])


# ── Schemas ───────────────────────────────────────────────────

class CreateInvestigation(BaseModel):
    type: Optional[Literal["text", "url", "message", "email"]] = Field(
        None, description="Input kind. Omit when `demo_id` is given.")
    content: Optional[str] = Field(None, description="The suspicious content, or the URL for type=url.")
    demo_id: Optional[str] = Field(None, description="Run a synthetic sample from /demo/samples instead.")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "type": "message",
                "content": "Congratulations! You have won Rs 50,000. Click this link to claim your reward: http://example-reward.top/claim",
            }]
        }
    }


class ContentBody(BaseModel):
    content: str = Field(..., min_length=1)


class UrlBody(BaseModel):
    url: str = Field(..., min_length=3, max_length=2048)


class CreatedResponse(BaseModel):
    id: str
    public_id: str
    status: str
    executor: str
    links: dict


def _raise(exc: InvestigationError):
    raise ApiError(exc.status, exc.code, exc.message)


# ── Investigations ────────────────────────────────────────────

@investigations_router.post("", status_code=202, response_model=CreatedResponse)
@expensive_limit
def create(
    request: Request,
    payload: CreateInvestigation,
    background: BackgroundTasks,
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
):
    """
    Open an investigation and start its pipeline.

    Returns immediately with the investigation id; poll `GET /investigations/{id}`
    for status, the stage timeline and, once `COMPLETED`, the structured result.
    """
    try:
        inv = service.create_investigation(
            session, principal, type=payload.type, content=payload.content, demo_id=payload.demo_id,
        )
    except InvestigationError as exc:
        _raise(exc)
    try:
        executor = service.dispatch(inv, background=background)
    except InvestigationError as exc:
        # Never leave a QUEUED record that nothing will ever pick up.
        inv.status = "FAILED"
        inv.error = exc.message
        session.commit()
        _raise(exc)
    session.refresh(inv)
    return CreatedResponse(
        id=str(inv.id), public_id=inv.public_id, status=inv.status, executor=executor,
        links={"self": f"/api/v1/investigations/{inv.id}",
               "events": f"/api/v1/investigations/{inv.id}/events"},
    )


@investigations_router.get("")
def list_investigations(
    q: str = Query("", max_length=200, description="Public id, excerpt, classification or SHA-256"),
    status: str = Query(""),
    risk_level: str = Query(""),
    type: str = Query(""),
    sort: Literal["-created_at", "created_at", "-risk_score", "risk_score"] = "-created_at",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
):
    rows, total = service.list_investigations(
        session, principal, q=q, status=status, risk_level=risk_level, type=type,
        sort=sort, page=page, page_size=page_size,
    )
    return {"items": [service.summary(r) for r in rows], "total": total,
            "page": page, "page_size": page_size}


def _find(session, principal, ident):
    try:
        return service.find(session, principal, ident)
    except InvestigationError as exc:
        _raise(exc)


@investigations_router.get("/{ident}")
def get_investigation(
    ident: str,
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
):
    """Full investigation: summary, timeline, risk factors, predictions, input and result."""
    return service.detail(_find(session, principal, ident), principal)


@investigations_router.get("/{ident}/events")
def get_events(
    ident: str,
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
):
    inv = _find(session, principal, ident)
    return {"status": inv.status, "current_stage": inv.current_stage, "events": service.timeline(inv)}


def _csv_cell(value) -> str:
    # Spreadsheet formula injection: evidence excerpts are attacker-written.
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@investigations_router.get("/{ident}/export")
def export(
    ident: str,
    format: Literal["json", "csv"] = "json",
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
):
    """
    Download the investigation. The export carries the redacted input only --
    an exported file travels further than the account it came from.
    """
    inv = _find(session, principal, ident)
    filename = f"{inv.public_id}.{format}"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

    if format == "json":
        body = service.detail(inv, principal)
        body["input"]["content"] = None
        return JSONResponse(body, headers=headers)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["investigation", "code", "title", "family", "severity", "provenance",
                     "engine", "engine_version", "points", "confidence", "evidence"])
    for f in sorted(inv.risk_factors, key=lambda f: -f.points):
        writer.writerow([_csv_cell(v) for v in (
            inv.public_id, f.code, f.title, f.family, f.severity, f.provenance,
            f.engine, f.engine_version, f.points, f.confidence, f.evidence,
        )])
    return Response(buffer.getvalue(), media_type="text/csv", headers=headers)


@investigations_router.delete("/{ident}", status_code=204)
def delete_investigation(
    ident: str,
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
):
    """Delete the investigation and everything derived from it (inputs, timeline, factors, predictions)."""
    service.delete(session, principal, _find(session, principal, ident))
    return Response(status_code=204)


# ── Synchronous analysis ──────────────────────────────────────

def _analyze_inline(session, principal, kind: str, content: str):
    try:
        inv = service.create_investigation(session, principal, type=kind, content=content)
        service.dispatch(inv, mode="inline")
    except InvestigationError as exc:
        _raise(exc)
    session.expire_all()
    return service.detail(service.find(session, principal, str(inv.id)), principal)


@analyze_v2_router.post("/text")
@expensive_limit
def analyze_text(request: Request, body: ContentBody, principal: Principal = Depends(require_principal),
                 session: Session = Depends(get_session)):
    """Investigate free text and return the completed result in one call."""
    return _analyze_inline(session, principal, "text", body.content)


@analyze_v2_router.post("/message")
@expensive_limit
def analyze_message(request: Request, body: ContentBody, principal: Principal = Depends(require_principal),
                    session: Session = Depends(get_session)):
    """Investigate an SMS, chat message or post."""
    return _analyze_inline(session, principal, "message", body.content)


@analyze_v2_router.post("/email")
@expensive_limit
def analyze_email(request: Request, body: ContentBody, principal: Principal = Depends(require_principal),
                  session: Session = Depends(get_session)):
    """Investigate an email, headers included when available."""
    return _analyze_inline(session, principal, "email", body.content)


@analyze_v2_router.post("/url")
@expensive_limit
def analyze_url(request: Request, body: UrlBody, principal: Principal = Depends(require_principal),
                session: Session = Depends(get_session)):
    """Investigate a single URL."""
    return _analyze_inline(session, principal, "url", body.url)


# ── Platform ──────────────────────────────────────────────────

@platform_router.get("/dashboard/summary")
def dashboard_summary(
    days: int = Query(30, ge=1, le=365),
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
):
    """Aggregates over real stored investigations. Nothing here is a hard-coded figure."""
    return service.dashboard(session, principal, days=days)


@platform_router.get("/engines")
def engines(principal: Principal = Depends(require_principal)):
    from truthshield.investigations.engines import catalogue
    from truthshield.investigations.risk_config import load_risk_config

    return {"engines": catalogue(), "risk": load_risk_config().as_dict()}


@platform_router.get("/demo/samples")
def demo_samples():
    return demo.catalogue()


@platform_router.get("/system/health")
def system_health(session: Session = Depends(get_session)):
    """Health plus what this deployment can actually do. Public, like /health."""
    from truthshield.api.routes import health
    from truthshield.infra.models import Investigation
    from truthshield.investigations.engines import catalogue
    from truthshield.investigations.risk_config import load_risk_config
    from truthshield.settings import get_settings

    settings = get_settings()
    base = health().model_dump()
    try:
        completed = session.query(Investigation).filter(Investigation.status == "COMPLETED").count()
    except Exception:
        completed = None
    return {
        **base,
        "engines": catalogue(),
        "risk_config_version": load_risk_config().version,
        "investigations": {
            "executor": settings.INVESTIGATION_EXECUTOR,
            "offline_mode": settings.OFFLINE_MODE,
            "page_fetch": settings.URL_FETCH_ENABLED and settings.network_allowed,
            "evidence_retrieval": settings.EVIDENCE_RETRIEVAL_ENABLED and settings.network_allowed,
            "completed_total": completed,
        },
        "languages": ["en", "hi", "ta"],
    }


# ── Admin ─────────────────────────────────────────────────────

class UserUpdate(BaseModel):
    role: Optional[Literal["USER", "ANALYST", "ADMIN"]] = None
    is_active: Optional[bool] = None


def _user_out(u: User) -> dict:
    return {"id": str(u.id), "email": u.email, "role": u.role, "is_active": u.is_active,
            "created_at": service.iso(u.created_at),
            "last_login_at": service.iso(u.last_login_at)}


@admin_router.get("/users")
def admin_users(
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
    principal: Principal = Depends(require_role("ADMIN")),
    session: Session = Depends(get_session),
):
    query = session.query(User).order_by(User.created_at.desc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [_user_out(u) for u in rows], "total": total, "page": page, "page_size": page_size}


@admin_router.patch("/users/{user_id}")
def admin_update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    principal: Principal = Depends(require_role("ADMIN")),
    session: Session = Depends(get_session),
):
    user = session.get(User, user_id)
    if user is None:
        raise ApiError(404, "NOT_FOUND", "User not found.")
    if user.id == principal.user_id:
        # An administrator removing their own access is how a deployment ends
        # up with no administrator at all.
        raise ApiError(400, "BAD_REQUEST", "You cannot change your own role or status.")

    changes = {}
    if body.role is not None and body.role != user.role:
        changes["role"] = {"from": user.role, "to": body.role}
        user.role = body.role
    if body.is_active is not None and body.is_active != user.is_active:
        changes["is_active"] = {"from": user.is_active, "to": body.is_active}
        user.is_active = body.is_active
    session.commit()
    if changes:
        record_audit(session, principal, "admin.user.update", f"user:{user.id}", changes)
    return _user_out(user)


@admin_router.get("/audit-logs")
def admin_audit_logs(
    limit: int = Query(100, ge=1, le=500),
    principal: Principal = Depends(require_role("ADMIN")),
    session: Session = Depends(get_session),
):
    rows = session.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return {"items": [
        {"id": str(r.id), "action": r.action, "actor_id": str(r.actor_id) if r.actor_id else None,
         "detail": r.detail, "created_at": service.iso(r.created_at)}
        for r in rows
    ]}
