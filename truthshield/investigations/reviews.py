"""
Human review: submitter feedback, appeals, reviewer decisions, and the
accuracy those decisions make measurable.

Rules this module holds to:

* A review never rewrites the investigation. The score, level and claim
  assessments stay what the engines produced; a reviewer's decision sits
  beside them, attributed and timestamped.
* A reviewer cannot decide an appeal they filed themselves.
* Comments are redacted before storage, like every other submitted text.
* Accuracy is computed only from reviewer decisions, with every rate next to
  its denominator, and with the selection bias stated: reviewed cases are the
  ones someone disputed or chose to comment on, not a random sample.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from truthshield.infra.models import Investigation, InvestigationReview
from truthshield.investigations.risk import band_for
from truthshield.investigations.service import InvestigationError, iso
from truthshield.services.auth import Principal

USER_LABELS = ("fraud", "legitimate", "unsure")
REVIEWER_LABELS = ("fraud", "legitimate", "inconclusive")
# The same line the offline evaluation uses: MEDIUM or above is "flagged".
FLAGGED_LEVELS = ("MEDIUM", "HIGH", "CRITICAL")
MAX_COMMENT = 2000


def _redact(text: Optional[str]) -> Optional[str]:
    from truthshield.fraud.privacy import redact

    text = (text or "").strip()[:MAX_COMMENT]
    return redact(text)[0] if text else None


def submit(session: Session, principal: Principal, inv: Investigation, *,
           label: str, comment: Optional[str] = None, appeal: bool = False) -> InvestigationReview:
    if inv.status != "COMPLETED":
        raise InvestigationError(409, "NOT_READY", "Feedback can be given once the investigation has completed.")
    if label not in USER_LABELS:
        raise InvestigationError(400, "BAD_REQUEST", f"label must be one of: {', '.join(USER_LABELS)}.")

    kind = "appeal" if appeal else "feedback"
    existing = None
    if appeal:
        if any(r.kind == "appeal" and r.status == "open" for r in inv.reviews):
            raise InvestigationError(409, "APPEAL_OPEN", "An appeal on this investigation is already awaiting review.")
    else:
        # One piece of feedback per person per investigation; a second one
        # replaces the first rather than counting twice.
        existing = next((r for r in inv.reviews if r.kind == "feedback"
                         and r.author_id == principal.user_id and r.status == "recorded"), None)

    review = existing or InvestigationReview(investigation_id=inv.id, author_id=principal.user_id, kind=kind)
    review.user_label = label
    review.comment = _redact(comment)
    review.status = "open" if appeal else "recorded"
    review.system_score = inv.risk_score
    review.system_level = inv.risk_level
    review.system_confidence = inv.confidence
    review.system_classification = inv.classification
    review.system_config_version = (((inv.result or {}).get("risk") or {}).get("config") or {}).get("version")
    if existing is None:
        session.add(review)
    session.commit()
    session.refresh(review)

    from truthshield.services.audit import record
    record(session, principal, f"investigation.{kind}", f"investigation:{inv.public_id}",
           {"label": label, "review_id": str(review.id)})
    return review


def resolve(session: Session, principal: Principal, review: InvestigationReview, *,
            label: str, note: Optional[str] = None) -> InvestigationReview:
    if label not in REVIEWER_LABELS:
        raise InvestigationError(400, "BAD_REQUEST", f"label must be one of: {', '.join(REVIEWER_LABELS)}.")
    if review.author_id is not None and review.author_id == principal.user_id:
        raise InvestigationError(403, "FORBIDDEN", "You cannot review your own feedback or appeal.")
    previous = review.reviewer_label
    review.reviewer_id = principal.user_id
    review.reviewer_label = label
    review.reviewer_note = _redact(note)
    review.status = "resolved"
    review.resolved_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(review)

    from truthshield.services.audit import record
    record(session, principal, "investigation.review.resolve", f"review:{review.id}",
           {"label": label, "previous": previous})
    return review


def find(session: Session, review_id) -> InvestigationReview:
    import uuid

    try:
        review = session.get(InvestigationReview, uuid.UUID(str(review_id)))
    except ValueError:
        review = None
    if review is None:
        raise InvestigationError(404, "NOT_FOUND", "Review not found.")
    return review


def out(review: InvestigationReview, *, with_investigation: bool = False) -> dict:
    data = {
        "id": str(review.id),
        "kind": review.kind,
        "status": review.status,
        "user_label": review.user_label,
        "comment": review.comment,
        "system": {
            "score": review.system_score, "level": review.system_level,
            "confidence": review.system_confidence, "classification": review.system_classification,
            "config_version": review.system_config_version,
        },
        "reviewer_label": review.reviewer_label,
        "reviewer_note": review.reviewer_note,
        "resolved_at": iso(review.resolved_at),
        "created_at": iso(review.created_at),
        "note": "A reviewer's decision is recorded beside the automated result; it does not change it.",
    }
    if with_investigation:
        inv = review.investigation
        source = inv.inputs[0] if inv.inputs else None
        data["investigation"] = {
            "id": str(inv.id), "public_id": inv.public_id, "type": inv.type,
            "excerpt": inv.excerpt,
            # Reviewers work from the redacted copy, never the original.
            "redacted_input": source.redacted_content if source else None,
            "result": inv.result,
        }
    return data


def queue(session: Session, *, status: str = "open", kind: Optional[str] = None,
          page: int = 1, page_size: int = 50) -> dict:
    query = session.query(InvestigationReview)
    if status != "all":
        query = query.filter(InvestigationReview.status == status)
    if kind:
        query = query.filter(InvestigationReview.kind == kind)
    total = query.count()
    rows = (query.order_by(InvestigationReview.created_at.asc())
            .offset((page - 1) * page_size).limit(page_size).all())
    return {"items": [out(r, with_investigation=False) | {"investigation_public_id": r.investigation.public_id}
                      for r in rows],
            "total": total, "page": page, "page_size": page_size}


def _rate(num: int, den: int) -> Optional[float]:
    return round(num / den, 3) if den else None


def accuracy(session: Session, *, days: int = 90) -> dict:
    """
    How the automated result compares with reviewer decisions.

    One decision per investigation (the latest resolved one). "inconclusive"
    reviewer decisions are counted but left out of the confusion matrix.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (session.query(InvestigationReview)
            .filter(InvestigationReview.status == "resolved", InvestigationReview.resolved_at >= since)
            .order_by(InvestigationReview.resolved_at.asc()).all())
    latest = {}
    for r in rows:
        latest[r.investigation_id] = r

    tp = fp = tn = fn = inconclusive = 0
    bands: dict = {}
    for r in latest.values():
        if r.reviewer_label == "inconclusive":
            inconclusive += 1
            continue
        flagged = r.system_level in FLAGGED_LEVELS
        fraud = r.reviewer_label == "fraud"
        tp += flagged and fraud
        fp += flagged and not fraud
        fn += (not flagged) and fraud
        tn += (not flagged) and not fraud
        band = band_for(r.system_confidence) if r.system_confidence is not None else "UNKNOWN"
        b = bands.setdefault(band, {"reviewed": 0, "agreed": 0})
        b["reviewed"] += 1
        b["agreed"] += flagged == fraud

    decided = tp + fp + tn + fn
    feedback = (session.query(InvestigationReview)
                .filter(InvestigationReview.created_at >= since,
                        InvestigationReview.user_label.in_(("fraud", "legitimate"))).all())
    user_agree = sum(1 for r in feedback if (r.system_level in FLAGGED_LEVELS) == (r.user_label == "fraud"))

    return {
        "window_days": days,
        "reviewed_investigations": len(latest),
        "decided": decided,
        "reviewer_inconclusive": inconclusive,
        "confusion": {"true_positive": tp, "false_positive": fp, "true_negative": tn, "false_negative": fn},
        "precision": _rate(tp, tp + fp),
        "recall": _rate(tp, tp + fn),
        "false_positive_rate": _rate(fp, fp + tn),
        "agreement": _rate(tp + tn, decided),
        "by_confidence_band": {
            k: {**v, "agreement": _rate(v["agreed"], v["reviewed"])} for k, v in sorted(bands.items())
        },
        "submitter_feedback": {
            "count": len(feedback),
            "agreement_with_system": _rate(user_agree, len(feedback)),
            "note": "Unverified opinions of the people who submitted the content; not ground truth.",
        },
        "flagged_means": "risk level MEDIUM or above",
        "caveats": [
            "Reviewed cases are those someone disputed or commented on, not a random sample; "
            "these rates describe that set and are not an estimate of overall accuracy.",
            "Rates are null when their denominator is zero. Read every rate with its counts.",
        ],
    }
