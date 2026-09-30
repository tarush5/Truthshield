"""
Investigation service: intake, access control, queries, aggregates.

The HTTP layer stays thin; everything that decides who may see what, and how
an input becomes an investigation, lives here.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from urllib.parse import urlparse

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from truthshield.infra.models import Investigation, InvestigationInput, RiskFactor
from truthshield.investigations import demo
from truthshield.investigations.ids import next_public_id
from truthshield.investigations.types import InvestigationStatus, InvestigationType
from truthshield.services.auth import Principal

logger = logging.getLogger(__name__)

SORTS = {
    "-created_at": Investigation.created_at.desc(),
    "created_at": Investigation.created_at.asc(),
    "-risk_score": Investigation.risk_score.desc(),
    "risk_score": Investigation.risk_score.asc(),
}


class InvestigationError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


# ── Intake ────────────────────────────────────────────────────

def _normalise_url(raw: str) -> str:
    value = raw.strip()
    candidate = value if "://" in value else f"http://{value}"
    parsed = urlparse(candidate)
    if parsed.scheme.lower() not in ("http", "https"):
        raise InvestigationError(400, "UNSUPPORTED_INPUT", "Only http and https links can be analysed.")
    if not parsed.hostname or " " in value:
        raise InvestigationError(400, "UNSUPPORTED_INPUT", "That does not look like a web address.")
    return candidate


def create_investigation(
    session: Session,
    principal: Principal,
    *,
    type: Optional[str] = None,
    content: Optional[str] = None,
    demo_id: Optional[str] = None,
) -> Investigation:
    from truthshield.fraud.privacy import redact, summarise
    from truthshield.settings import get_settings

    settings = get_settings()
    is_demo = False

    if demo_id:
        sample = demo.get_sample(demo_id)
        if sample is None:
            raise InvestigationError(404, "NOT_FOUND", "Unknown demo sample.")
        type, content, is_demo = sample["type"], sample["content"], True

    try:
        kind = InvestigationType((type or "").lower())
    except ValueError:
        raise InvestigationError(
            400, "UNSUPPORTED_INPUT",
            "Unsupported investigation type. Phase 1 supports: text, url, message, email.",
        )

    content = (content or "").strip()
    if not content:
        raise InvestigationError(400, "BAD_REQUEST", "Nothing to investigate: the content is empty.")
    if len(content) > settings.MAX_TEXT_LENGTH:
        raise InvestigationError(
            413, "PAYLOAD_TOO_LARGE", f"Content exceeds the {settings.MAX_TEXT_LENGTH} character limit.",
        )
    if kind is InvestigationType.URL:
        content = _normalise_url(content)

    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    redacted, redactions = redact(content)

    inv = Investigation(
        public_id=next_public_id(session),
        user_id=principal.user_id,
        org_id=principal.org_id,
        type=kind.value,
        status=InvestigationStatus.QUEUED.value,
        input_sha256=digest,
        excerpt=" ".join(redacted.split())[:240],
        is_demo=is_demo,
    )
    session.add(inv)
    session.flush()
    session.add(InvestigationInput(
        investigation_id=inv.id,
        kind=kind.value,
        content=content,
        redacted_content=redacted,
        sha256=digest,
        size_bytes=len(content.encode("utf-8")),
        mime_type="text/plain",
        meta={"redactions": summarise(redactions), "demo_id": demo_id},
    ))
    session.commit()
    session.refresh(inv)

    from truthshield.services.audit import record
    record(session, principal, "investigation.create", f"investigation:{inv.public_id}",
           {"type": kind.value, "demo": is_demo})
    return inv


def dispatch(inv: Investigation, *, background=None, mode: Optional[str] = None) -> str:
    """Hand the investigation to its executor. Returns the executor used."""
    from truthshield.investigations.pipeline import InvestigationRunner
    from truthshield.settings import get_settings

    mode = mode or get_settings().INVESTIGATION_EXECUTOR

    if mode == "celery":
        from truthshield.infra.celery_app import broker_reachable
        from truthshield.investigations.tasks import run_investigation

        if not broker_reachable():
            raise InvestigationError(503, "UNAVAILABLE",
                                     "The analysis queue is unavailable. Please retry shortly.")
        run_investigation.delay(str(inv.id))
        return "celery"

    if mode == "background" and background is not None:
        background.add_task(InvestigationRunner().run, inv.id)
        return "background"

    InvestigationRunner().run(inv.id)
    return "inline"


# ── Access ────────────────────────────────────────────────────

def _scoped(session: Session, principal: Principal):
    query = session.query(Investigation)
    if principal.role != "ADMIN":
        query = query.filter(Investigation.user_id == principal.user_id)
    return query


def find(session: Session, principal: Principal, ident: str) -> Investigation:
    query = _scoped(session, principal)
    inv = None
    try:
        inv = query.filter(Investigation.id == uuid.UUID(ident)).first()
    except ValueError:
        inv = query.filter(Investigation.public_id == ident.upper()).first()
    if inv is None:
        # Same answer for "does not exist" and "not yours".
        raise InvestigationError(404, "NOT_FOUND", "Investigation not found.")
    return inv


def list_investigations(
    session: Session, principal: Principal, *, q: str = "", status: str = "", risk_level: str = "",
    type: str = "", sort: str = "-created_at", page: int = 1, page_size: int = 20,
) -> Tuple[list, int]:
    query = _scoped(session, principal)
    if q:
        term = q.strip()
        like = f"%{term}%"
        query = query.filter(or_(
            Investigation.public_id.ilike(like),
            Investigation.excerpt.ilike(like),
            Investigation.input_sha256 == term.lower(),
            Investigation.classification.ilike(like),
        ))
    if status:
        query = query.filter(Investigation.status == status.upper())
    if risk_level:
        query = query.filter(Investigation.risk_level == risk_level.upper())
    if type:
        query = query.filter(Investigation.type == type.lower())

    total = query.count()
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    rows = (
        query.order_by(SORTS.get(sort, SORTS["-created_at"]), Investigation.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return rows, total


def delete(session: Session, principal: Principal, inv: Investigation) -> None:
    public_id = inv.public_id
    session.delete(inv)
    session.commit()
    from truthshield.services.audit import record
    record(session, principal, "investigation.delete", f"investigation:{public_id}", {})


# ── Serialisation ─────────────────────────────────────────────

def iso(value: Optional[datetime]) -> Optional[str]:
    """
    ISO-8601 with an explicit UTC offset, always.

    SQLite hands back naive datetimes even for timezone-aware columns. Sent
    without an offset, a browser parses them as *local* time, so a report
    written a minute ago read as "6h ago" in IST.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def summary(inv: Investigation) -> dict:
    return {
        "id": str(inv.id),
        "public_id": inv.public_id,
        "type": inv.type,
        "status": inv.status,
        "current_stage": inv.current_stage,
        "risk_score": inv.risk_score,
        "risk_level": inv.risk_level,
        "confidence": inv.confidence,
        "confidence_band": inv.confidence_band,
        "classification": inv.classification,
        "language": inv.language,
        "excerpt": inv.excerpt,
        "input_sha256": inv.input_sha256,
        "is_demo": inv.is_demo,
        "processing_ms": inv.processing_ms,
        "error": inv.error,
        "created_at": iso(inv.created_at),
        "completed_at": iso(inv.completed_at),
    }


def timeline(inv: Investigation) -> list:
    return [
        {
            "seq": e.seq, "stage": e.stage, "status": e.status, "service": e.service,
            "message": e.message, "started_at": iso(e.started_at),
            "finished_at": iso(e.finished_at),
            "duration_ms": e.duration_ms,
        }
        for e in sorted(inv.events, key=lambda e: e.seq)
    ]


def detail(inv: Investigation, principal: Principal) -> dict:
    source = inv.inputs[0] if inv.inputs else None
    owner = principal.role == "ADMIN" or inv.user_id == principal.user_id
    return {
        **summary(inv),
        "timeline": timeline(inv),
        "risk_factors": [
            {"code": f.code, "title": f.title, "family": f.family, "severity": f.severity,
             "provenance": f.provenance, "engine": f.engine, "engine_version": f.engine_version,
             "points": f.points, "confidence": f.confidence, "evidence": f.evidence}
            for f in sorted(inv.risk_factors, key=lambda f: -f.points)
        ],
        "model_predictions": [
            {"model_name": p.model_name, "model_version": p.model_version, "model_kind": p.model_kind,
             "task": p.task, "input_sha256": p.input_sha256, "prediction": p.prediction,
             "confidence": p.confidence, "created_at": iso(p.created_at)}
            for p in inv.predictions
        ],
        "input": {
            "kind": source.kind if source else inv.type,
            "sha256": source.sha256 if source else inv.input_sha256,
            "size_bytes": source.size_bytes if source else 0,
            # The original is the submitter's own data; nobody else sees it.
            "content": source.content if (source and owner) else None,
            "redacted": source.redacted_content if source else None,
        },
        "result": inv.result,
    }


# ── Aggregates ────────────────────────────────────────────────

def _percentile(values, fraction: float) -> Optional[int]:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(fraction * (len(ordered) - 1)))))
    return int(ordered[index])


def dashboard(session: Session, principal: Principal, *, days: int = 30) -> dict:
    days = max(1, min(days, 365))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    scoped = _scoped(session, principal)

    rows = (
        scoped.filter(Investigation.created_at >= since)
        .with_entities(
            Investigation.created_at, Investigation.status, Investigation.risk_level,
            Investigation.risk_score, Investigation.type, Investigation.classification,
            Investigation.processing_ms,
        )
        .limit(20_000)
        .all()
    )

    completed = [r for r in rows if r.status == InvestigationStatus.COMPLETED.value]
    levels = Counter(r.risk_level for r in completed)
    per_day = defaultdict(lambda: {"total": 0, "high_or_critical": 0})
    for r in rows:
        created = r.created_at if r.created_at.tzinfo else r.created_at.replace(tzinfo=timezone.utc)
        key = created.date().isoformat()
        per_day[key]["total"] += 1
        if r.risk_level in ("HIGH", "CRITICAL"):
            per_day[key]["high_or_critical"] += 1

    volume = []
    for offset in range(days - 1, -1, -1):
        day = (datetime.now(timezone.utc) - timedelta(days=offset)).date().isoformat()
        volume.append({"date": day, **per_day.get(day, {"total": 0, "high_or_critical": 0})})

    latencies = [r.processing_ms for r in completed if r.processing_ms is not None]
    scores = [r.risk_score for r in completed if r.risk_score is not None]

    ids = [i for (i,) in scoped.filter(Investigation.created_at >= since).with_entities(Investigation.id).all()]
    factor_rows = []
    if ids:
        factor_rows = (
            session.query(RiskFactor.code, RiskFactor.title, func.count(RiskFactor.id))
            .filter(RiskFactor.investigation_id.in_(ids[:5000]), RiskFactor.points > 0)
            .group_by(RiskFactor.code, RiskFactor.title)
            .order_by(func.count(RiskFactor.id).desc())
            .limit(8)
            .all()
        )

    recent = scoped.order_by(Investigation.created_at.desc()).limit(8).all()

    return {
        "window_days": days,
        "scope": "all" if principal.role == "ADMIN" else "own",
        "totals": {
            "investigations": len(rows),
            "completed": len(completed),
            "failed": sum(1 for r in rows if r.status == InvestigationStatus.FAILED.value),
            "in_progress": sum(1 for r in rows if not InvestigationStatus(r.status).is_terminal),
            "all_time": scoped.count(),
        },
        "risk_levels": {lvl: levels.get(lvl, 0) for lvl in ("LOW", "MEDIUM", "HIGH", "CRITICAL")},
        "by_type": dict(Counter(r.type for r in rows)),
        "by_classification": dict(Counter(r.classification for r in completed if r.classification)),
        "average_risk": round(sum(scores) / len(scores), 1) if scores else None,
        "latency_ms": {
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
            "p99": _percentile(latencies, 0.99),
            "samples": len(latencies),
        },
        "volume": volume,
        "top_risk_factors": [{"code": c, "title": t, "count": n} for c, t, n in factor_rows],
        "recent": [summary(r) for r in recent],
    }
