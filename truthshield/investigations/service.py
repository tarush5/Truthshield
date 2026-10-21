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
from sqlalchemy.orm import Session, defer

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
    existing = recent_duplicate(session, principal, digest, kind.value)
    if existing is not None:
        return existing
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


def recent_duplicate(session: Session, principal: Principal, digest: str, kind: str) -> Optional[Investigation]:
    """
    The caller's own investigation of identical content from the last few
    seconds, if any.

    A double click or a client retry used to open a second investigation and
    run the whole pipeline twice. The match is the caller's, same type, same
    SHA-256, so two people submitting the same scam still get separate runs.
    The returned object is marked `deduplicated` so the caller does not
    dispatch it again.
    """
    from truthshield.settings import get_settings

    window = get_settings().INVESTIGATION_DEDUP_SECONDS
    if window <= 0:
        return None
    since = datetime.now(timezone.utc) - timedelta(seconds=window)
    inv = (
        session.query(Investigation)
        .filter(Investigation.user_id == principal.user_id, Investigation.input_sha256 == digest,
                Investigation.type == kind, Investigation.created_at >= since,
                # A retry after a failure must run again, not get the failure back.
                Investigation.status != InvestigationStatus.FAILED.value)
        .order_by(Investigation.created_at.desc())
        .first()
    )
    if inv is not None:
        inv.deduplicated = True
    return inv


def expire_stale(session: Session, *, ids=None) -> int:
    """
    Mark investigations that can no longer finish as FAILED.

    A run whose worker died (a killed Celery process, an API restart under the
    background executor) stayed PROCESSING forever, and the result page polled
    it forever. Runs that started more than INVESTIGATION_STALE_MINUTES ago,
    or are still QUEUED after INVESTIGATION_QUEUE_TIMEOUT_MINUTES, are failed
    with a message saying where they stopped. Pass `ids` to limit the check to
    the rows about to be shown. Returns how many were marked.
    """
    from sqlalchemy import and_

    from truthshield.settings import get_settings

    settings = get_settings()
    now = datetime.now(timezone.utc)
    running_since = now - timedelta(minutes=settings.INVESTIGATION_STALE_MINUTES)
    queued_since = now - timedelta(minutes=settings.INVESTIGATION_QUEUE_TIMEOUT_MINUTES)
    queued = InvestigationStatus.QUEUED.value
    running = [s.value for s in InvestigationStatus if not s.is_terminal and s is not InvestigationStatus.QUEUED]

    query = session.query(Investigation).filter(or_(
        and_(Investigation.status.in_(running),
             func.coalesce(Investigation.started_at, Investigation.created_at) < running_since),
        and_(Investigation.status == queued, Investigation.created_at < queued_since),
    ))
    if ids is not None:
        ids = list(ids)
        if not ids:
            return 0
        query = query.filter(Investigation.id.in_(ids))

    stale = query.all()
    for inv in stale:
        where = (inv.current_stage or "").replace("_", " ").lower()
        inv.error = (
            f"The analysis stopped{' during ' + where if where else ''} and did not finish "
            "(the worker was interrupted). Please submit it again."
            if inv.status != queued else
            "The analysis was queued but never started (no worker picked it up). Please submit it again."
        )
        inv.status = InvestigationStatus.FAILED.value
        inv.current_stage = None
        inv.completed_at = now
    if stale:
        session.commit()
        logger.warning("Marked %d stale investigation(s) as failed", len(stale))
    return len(stale)


def dispatch(inv: Investigation, *, background=None, mode: Optional[str] = None) -> str:
    """Hand the investigation to its executor. Returns the executor used."""
    from truthshield.investigations.pipeline import InvestigationRunner
    from truthshield.settings import get_settings

    if getattr(inv, "deduplicated", False):
        return "existing"  # already dispatched by the first of the duplicate requests
    mode = mode or get_settings().INVESTIGATION_EXECUTOR

    if mode == "celery":
        from truthshield.infra.celery_app import broker_reachable
        from truthshield.investigations.tasks import run_investigation

        unavailable = InvestigationError(503, "UNAVAILABLE",
                                         "The analysis queue is unavailable. Please retry shortly.")
        if not broker_reachable():
            raise unavailable
        try:
            run_investigation.delay(str(inv.id))
        except Exception as exc:
            # The reachability answer is cached for a few seconds; a broker
            # that went down inside that window fails here instead.
            logger.warning("Could not enqueue investigation %s: %s", inv.public_id, type(exc).__name__)
            broker_reachable(fresh=True)
            raise unavailable from exc
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
    if not InvestigationStatus(inv.status).is_terminal:
        # The result page polls this: a dead run must end, not spin forever.
        expire_stale(session, ids=[inv.id])
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
        # Summaries never read `result` (the full report, often tens of kB);
        # leaving it out keeps a page of 100 rows from loading megabytes.
        query.options(defer(Investigation.result))
        .order_by(SORTS.get(sort, SORTS["-created_at"]), Investigation.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    unfinished = [r.id for r in rows if not InvestigationStatus(r.status).is_terminal]
    if unfinished:
        expire_stale(session, ids=unfinished)
    return rows, total


def create_file_investigation(session: Session, principal: Principal, stored) -> Investigation:
    """An investigation over an uploaded file already validated and stored by `files.receive`."""
    existing = recent_duplicate(session, principal, stored.sha256, stored.investigation_type)
    if existing is not None:
        return existing  # the stored copy is content-addressed: nothing extra was kept
    inv = Investigation(
        public_id=next_public_id(session),
        user_id=principal.user_id,
        org_id=principal.org_id,
        type=stored.investigation_type,
        status=InvestigationStatus.QUEUED.value,
        input_sha256=stored.sha256,
        excerpt=f"{stored.filename} ({stored.size / 1024:,.0f} KB)",
    )
    session.add(inv)
    session.flush()
    session.add(InvestigationInput(
        investigation_id=inv.id,
        kind=stored.investigation_type,
        content=None,
        redacted_content=None,
        sha256=stored.sha256,
        size_bytes=stored.size,
        mime_type=stored.mime_type,
        filename=stored.filename,
        storage_key=stored.key,
        meta={"sniffed_kind": stored.kind},
    ))
    session.commit()
    session.refresh(inv)

    from truthshield.services.audit import record
    record(session, principal, "investigation.create", f"investigation:{inv.public_id}",
           {"type": inv.type, "file_sha256": stored.sha256, "size": stored.size})
    return inv


def reanalyze(session: Session, principal: Principal, inv: Investigation) -> Investigation:
    """
    Run the current pipeline again over the input already stored for `inv`.

    A new investigation, never an overwrite: the earlier result stays as it
    was, and the new one records which investigation it re-ran, so the two
    can be compared (engine and config versions are in each result). The
    duplicate-submission guard does not apply -- re-running is the point.
    """
    if not InvestigationStatus(inv.status).is_terminal:
        raise InvestigationError(409, "NOT_READY", "This investigation is still running.")
    source = inv.inputs[0] if inv.inputs else None
    if source is None or (source.content is None and not source.storage_key):
        raise InvestigationError(409, "INPUT_UNAVAILABLE", "The original input is no longer stored.")
    if source.storage_key:
        from truthshield.storage import get_storage
        if not get_storage().exists(source.storage_key):
            raise InvestigationError(409, "INPUT_UNAVAILABLE", "The original file is no longer stored.")

    new = Investigation(
        public_id=next_public_id(session),
        # It stays in the owner's history even when an administrator re-runs it.
        user_id=inv.user_id,
        org_id=inv.org_id,
        type=inv.type,
        status=InvestigationStatus.QUEUED.value,
        input_sha256=inv.input_sha256,
        excerpt=inv.excerpt,
        is_demo=inv.is_demo,
    )
    session.add(new)
    session.flush()
    session.add(InvestigationInput(
        investigation_id=new.id,
        kind=source.kind,
        content=source.content,
        redacted_content=source.redacted_content,
        sha256=source.sha256,
        size_bytes=source.size_bytes,
        mime_type=source.mime_type,
        filename=source.filename,
        storage_key=source.storage_key,
        meta={**(source.meta or {}), "reanalysis_of": str(inv.id), "reanalysis_of_public_id": inv.public_id},
    ))
    session.commit()
    session.refresh(new)

    from truthshield.services.audit import record
    record(session, principal, "investigation.reanalyze", f"investigation:{new.public_id}",
           {"of": inv.public_id})
    return new


def _previous_run(inv: Investigation, source) -> Optional[dict]:
    meta = (source.meta or {}) if source else {}
    if not meta.get("reanalysis_of"):
        return None
    from sqlalchemy.orm import object_session

    prev = None
    session = object_session(inv)
    if session is not None:
        try:
            prev = session.get(Investigation, uuid.UUID(meta["reanalysis_of"]))
        except ValueError:
            prev = None
    if prev is None:
        return {"public_id": meta.get("reanalysis_of_public_id"), "available": False}
    risk = (prev.result or {}).get("risk") or {}
    return {
        "id": str(prev.id), "public_id": prev.public_id, "available": True,
        "status": prev.status, "risk_score": prev.risk_score, "risk_level": prev.risk_level,
        "confidence": prev.confidence, "classification": prev.classification,
        "config_version": (risk.get("config") or {}).get("version"),
        "schema_version": (prev.result or {}).get("schema_version"),
        "completed_at": iso(prev.completed_at),
    }


def _review_state(inv: Investigation) -> dict:
    reviews = list(inv.reviews)
    resolved = [r for r in reviews if r.status == "resolved"]
    latest = max(resolved, key=lambda r: r.resolved_at) if resolved else None
    return {
        "count": len(reviews),
        "open_appeal": any(r.kind == "appeal" and r.status == "open" for r in reviews),
        "reviewer_label": latest.reviewer_label if latest else None,
        "reviewed_at": iso(latest.resolved_at) if latest else None,
    }


def delete(session: Session, principal: Principal, inv: Investigation) -> None:
    public_id = inv.public_id
    keys = {i.storage_key for i in inv.inputs if i.storage_key}
    session.delete(inv)
    session.commit()

    # The file goes too, unless another investigation uploaded identical bytes
    # (storage is content-addressed, so they share one stored copy).
    from truthshield.storage import get_storage
    for key in keys:
        if not session.query(InvestigationInput).filter(InvestigationInput.storage_key == key).count():
            get_storage().delete(key)

    from truthshield.services.audit import record
    record(session, principal, "investigation.delete", f"investigation:{public_id}",
           {"files_deleted": len(keys)})


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
            "filename": source.filename if source else None,
            "mime_type": source.mime_type if source else None,
            "has_file": bool(source and source.storage_key and owner),
        },
        "result": inv.result,
        "reanalysis_of": _previous_run(inv, source),
        "review": _review_state(inv),
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
    expire_stale(session)  # "in progress" must not count runs that died
    scoped = _scoped(session, principal)

    # Aggregated in SQL, one row per (day, status, level, type, class):
    # tens of rows instead of one per investigation, read entirely from the
    # covering index ix_investigations_dashboard. Days are UTC dates.
    created = Investigation.created_at
    if session.get_bind().dialect.name == "postgresql":
        created = func.timezone("UTC", created)
    day_col = func.date(created).label("day")
    groups = (
        scoped.filter(Investigation.created_at >= since)
        .with_entities(
            day_col, Investigation.status, Investigation.risk_level, Investigation.type,
            Investigation.classification, func.count().label("n"),
            func.sum(Investigation.risk_score).label("score_sum"),
            func.count(Investigation.risk_score).label("scored"),
        )
        .group_by(day_col, Investigation.status, Investigation.risk_level, Investigation.type,
                  Investigation.classification)
        .all()
    )

    completed_value = InvestigationStatus.COMPLETED.value
    terminal = {s.value for s in InvestigationStatus if s.is_terminal}
    total = completed = failed = in_progress = scored = 0
    score_sum = 0.0
    levels: Counter = Counter()
    by_type: Counter = Counter()
    by_classification: Counter = Counter()
    per_day = defaultdict(lambda: {"total": 0, "high_or_critical": 0})
    for g in groups:
        total += g.n
        by_type[g.type] += g.n
        key = str(g.day)[:10]
        per_day[key]["total"] += g.n
        if g.risk_level in ("HIGH", "CRITICAL"):
            per_day[key]["high_or_critical"] += g.n
        if g.status == completed_value:
            completed += g.n
            levels[g.risk_level] += g.n
            if g.classification:
                by_classification[g.classification] += g.n
            score_sum += float(g.score_sum or 0)
            scored += g.scored
        elif g.status == InvestigationStatus.FAILED.value:
            failed += g.n
        if g.status not in terminal:
            in_progress += g.n

    volume = []
    for offset in range(days - 1, -1, -1):
        day = (datetime.now(timezone.utc) - timedelta(days=offset)).date().isoformat()
        volume.append({"date": day, **per_day.get(day, {"total": 0, "high_or_critical": 0})})

    # Percentiles need the values themselves. Filtered on the date range
    # only, so the covering index serves it; a status condition here makes
    # SQLite pick the status index and read every full row instead.
    latencies = [
        ms for status, ms in scoped.filter(Investigation.created_at >= since)
        .with_entities(Investigation.status, Investigation.processing_ms).all()
        if status == completed_value and ms is not None
    ]

    # One grouped query over a join, instead of fetching every id in the
    # window and sending them back as an IN list (capped, so it undercounted).
    factor_query = (
        session.query(RiskFactor.code, RiskFactor.title, func.count(RiskFactor.id))
        .join(Investigation, RiskFactor.investigation_id == Investigation.id)
        .filter(Investigation.created_at >= since, RiskFactor.points > 0)
    )
    if principal.role != "ADMIN":
        factor_query = factor_query.filter(Investigation.user_id == principal.user_id)
    factor_rows = (
        factor_query.group_by(RiskFactor.code, RiskFactor.title)
        .order_by(func.count(RiskFactor.id).desc())
        .limit(8)
        .all()
    )

    recent = scoped.options(defer(Investigation.result)).order_by(Investigation.created_at.desc()).limit(8).all()

    return {
        "window_days": days,
        "scope": "all" if principal.role == "ADMIN" else "own",
        "totals": {
            "investigations": total,
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "all_time": scoped.count(),
        },
        "risk_levels": {lvl: levels.get(lvl, 0) for lvl in ("LOW", "MEDIUM", "HIGH", "CRITICAL")},
        "by_type": dict(by_type),
        "by_classification": dict(by_classification),
        "average_risk": round(score_sum / scored, 1) if scored else None,
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


def scam_patterns(session: Session, principal: Principal, *, days: int = 30, limit: int = 15) -> dict:
    """
    Which risk factors and classifications are rising or falling: this
    window against the window of the same length before it.

    Counts of investigations, not of the world: they reflect what users chose
    to submit. A change on a handful of cases is noise, so each row carries
    both counts and the change is null when the earlier window was empty.
    """
    days = max(1, min(days, 365))
    now = datetime.now(timezone.utc)
    current_start, previous_start = now - timedelta(days=days), now - timedelta(days=2 * days)

    def factor_counts(start, end):
        query = (
            session.query(RiskFactor.code, RiskFactor.title, func.count(func.distinct(RiskFactor.investigation_id)))
            .join(Investigation, RiskFactor.investigation_id == Investigation.id)
            .filter(Investigation.created_at >= start, Investigation.created_at < end, RiskFactor.points > 0)
        )
        if principal.role != "ADMIN":
            query = query.filter(Investigation.user_id == principal.user_id)
        return {code: (title, n) for code, title, n in query.group_by(RiskFactor.code, RiskFactor.title).all()}

    def class_counts(start, end):
        rows = (_scoped(session, principal)
                .filter(Investigation.created_at >= start, Investigation.created_at < end,
                        Investigation.classification.isnot(None))
                .with_entities(Investigation.classification, func.count())
                .group_by(Investigation.classification).all())
        return dict(rows)

    def rows(current: dict, previous: dict):
        out = []
        for key in set(current) | set(previous):
            cur = current.get(key)
            prev = previous.get(key)
            cur_n = (cur[1] if isinstance(cur, tuple) else cur) or 0
            prev_n = (prev[1] if isinstance(prev, tuple) else prev) or 0
            out.append({
                "key": key,
                "title": (cur or prev)[0] if isinstance(cur or prev, tuple) else None,
                "current": cur_n,
                "previous": prev_n,
                "change": round((cur_n - prev_n) / prev_n, 2) if prev_n else None,
            })
        out.sort(key=lambda r: (-(r["current"] - r["previous"]), -r["current"], r["key"]))
        return out[:limit]

    return {
        "window_days": days,
        "scope": "all" if principal.role == "ADMIN" else "own",
        "current_window_start": iso(current_start),
        "previous_window_start": iso(previous_start),
        "risk_factors": rows(factor_counts(current_start, now), factor_counts(previous_start, current_start)),
        "classifications": rows(class_counts(current_start, now), class_counts(previous_start, current_start)),
        "note": "Counts of submitted investigations, not prevalence in the wild. Rising means submitted more often.",
    }
