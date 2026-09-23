"""
Aggregate views over what the system has actually done.

Five questions, each aggregated in the database rather than pulled into
Python -- these run over the whole reports table, and the difference between
a GROUP BY and a fetch-then-count is the difference between a dashboard and
an outage.

  **Volume and verdicts over time.** Daily buckets, verdicts as series.

  **Sources.** Which domains this system actually relies on, how credible it
  rates them, and how their evidence splits between supporting and refuting.
  A domain cited constantly at a low credibility score is worth an
  operator's attention.

  **Calibration.** Where readers disagreed with a verdict, broken out by what
  the verdict was. This is the only measurement here that can say the
  system is wrong rather than merely busy, so it is reported as a rate with
  its denominator attached: "3 of 4" and "300 of 400" are not the same
  finding, and a percentage alone hides which one you have.

  **Latency.** p50/p95 rather than a mean. A mean processing time over a
  network-bound workload is dominated by whatever the slowest upstream did
  and describes no actual request.

  **Confidence mix.** How often the engine commits versus abstains.

Date bucketing goes through `func.date()`, which SQLite, Postgres and
MySQL all implement -- `date_trunc` and `strftime` are each single-dialect,
and `CAST(x AS DATE)` is worse than either: SQLite has no date type, so the
cast silently yields a number and SQLAlchemy's result processor fails on it
at fetch time rather than at query time.

It returns a `date` on Postgres and a `YYYY-MM-DD` string on SQLite, so the
bucket key is normalised on read rather than assumed.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import case, func

from truthshield.infra.models import Evidence, Feedback, Report

logger = logging.getLogger(__name__)

# A dashboard default. Long enough to show a trend, short enough that the
# daily series stays readable without resampling.
DEFAULT_WINDOW_DAYS = 30
MAX_WINDOW_DAYS = 365

# Below this a rate is noise. A domain cited twice has no meaningful mean
# credibility, and reporting one invites a reader to act on it.
MIN_SAMPLES_FOR_RATE = 5

# Verdicts the engine issues when it declines to commit.
ABSTAINING = ("UNVERIFIED", "MISLEADING")

# How long a computed overview stays good for. Short enough that the
# dashboard tracks reality, long enough that a full scan happens once a
# minute per window rather than once per viewer. See `overview`.
OVERVIEW_CACHE_SECONDS = 60


def _window_start(days: int) -> datetime:
    days = max(1, min(int(days), MAX_WINDOW_DAYS))
    return datetime.now(timezone.utc) - timedelta(days=days)



def volume_over_time(session, *, days: int = DEFAULT_WINDOW_DAYS) -> dict:
    """
    Daily analysis counts, split by verdict.

    Returns dense buckets: days with no activity come back as zeros rather
    than as gaps, so a chart draws a flat line instead of interpolating
    across a quiet weekend and inventing a trend.
    """
    since = _window_start(days)
    day = func.date(Report.created_at).label("day")

    rows = (
        session.query(day, Report.verdict, func.count(Report.id))
        .filter(Report.status == "complete", Report.created_at >= since)
        .group_by(day, Report.verdict)
        .all()
    )

    by_day: dict = defaultdict(lambda: defaultdict(int))
    verdicts = set()
    for bucket, verdict, count in rows:
        key = bucket.isoformat() if hasattr(bucket, "isoformat") else str(bucket)
        by_day[key][verdict] = int(count)
        verdicts.add(verdict)

    span = max(1, min(int(days), MAX_WINDOW_DAYS))
    today = datetime.now(timezone.utc).date()
    series = []
    for offset in range(span - 1, -1, -1):
        key = (today - timedelta(days=offset)).isoformat()
        counts = by_day.get(key, {})
        series.append({
            "date": key,
            "total": sum(counts.values()),
            **{v: counts.get(v, 0) for v in sorted(verdicts)},
        })

    return {"series": series, "verdicts": sorted(verdicts), "days": span}


def source_leaderboard(session, *, days: int = DEFAULT_WINDOW_DAYS, limit: int = 15) -> dict:
    """
    The domains this system leans on, by how often evidence came from them.

    Stance counts are aggregated with a CASE rather than three queries; the
    supporting/refuting split is the interesting part, because a domain that
    only ever appears on one side of claims is a different kind of source
    from one that appears on both.
    """
    since = _window_start(days)

    rows = (
        session.query(
            Evidence.source_domain,
            func.count(Evidence.id).label("citations"),
            func.avg(Evidence.source_score).label("credibility"),
            func.sum(case((Evidence.stance == "SUPPORTS", 1), else_=0)).label("supports"),
            func.sum(case((Evidence.stance == "REFUTES", 1), else_=0)).label("refutes"),
        )
        .join(Report, Report.id == Evidence.report_id)
        .filter(Report.created_at >= since)
        .filter(Evidence.source_domain.isnot(None))
        .group_by(Evidence.source_domain)
        .order_by(func.count(Evidence.id).desc())
        .limit(limit)
        .all()
    )

    sources = []
    for domain, citations, credibility, supports, refutes in rows:
        citations = int(citations or 0)
        sources.append({
            "domain": domain,
            "citations": citations,
            "credibility": round(float(credibility or 0.0), 3),
            "supports": int(supports or 0),
            "refutes": int(refutes or 0),
            "neutral": citations - int(supports or 0) - int(refutes or 0),
            # Suppressed rather than shown small: a mean over three rows is
            # not a credibility rating, and rounding it to 3dp makes it look
            # like one.
            "reliable_sample": citations >= MIN_SAMPLES_FOR_RATE,
        })
    return {"sources": sources, "days": max(1, min(int(days), MAX_WINDOW_DAYS))}


def calibration(session, *, days: int = DEFAULT_WINDOW_DAYS) -> dict:
    """
    How often readers disagreed with a verdict, by verdict.

    Feedback is self-selected -- people who disagree are likelier to leave
    it -- so this is a signal to investigate, not an accuracy score. Every
    rate ships with the count it was computed from for exactly that reason,
    and `reliable_sample` marks the ones with enough rows to mean anything.
    """
    since = _window_start(days)

    rows = (
        session.query(
            Report.verdict,
            func.count(Feedback.id).label("total"),
            func.sum(
                case((func.upper(Feedback.user_verdict) == Report.verdict, 1), else_=0)
            ).label("agreed"),
        )
        .join(Feedback, Feedback.report_id == Report.id)
        .filter(Report.created_at >= since)
        .group_by(Report.verdict)
        .all()
    )

    breakdown = []
    total_feedback = total_agreed = 0
    for verdict, total, agreed in rows:
        total, agreed = int(total or 0), int(agreed or 0)
        total_feedback += total
        total_agreed += agreed
        breakdown.append({
            "verdict": verdict,
            "feedback_count": total,
            "agreed": agreed,
            "disagreed": total - agreed,
            "agreement_rate": round(agreed / total, 3) if total else None,
            "reliable_sample": total >= MIN_SAMPLES_FOR_RATE,
        })

    breakdown.sort(key=lambda row: row["feedback_count"], reverse=True)
    return {
        "by_verdict": breakdown,
        "feedback_count": total_feedback,
        "agreement_rate": round(total_agreed / total_feedback, 3) if total_feedback else None,
        "reliable_sample": total_feedback >= MIN_SAMPLES_FOR_RATE,
        "days": max(1, min(int(days), MAX_WINDOW_DAYS)),
    }


def latency(session, *, days: int = DEFAULT_WINDOW_DAYS) -> dict:
    """
    Processing-time percentiles.

    Percentiles are computed in Python over the window's durations. That is
    a deliberate trade: `percentile_cont` is Postgres-only and this has to
    run on SQLite too, and a window of durations is a single float column
    that stays small long after the payloads beside it do not.
    """
    since = _window_start(days)
    rows = (
        session.query(Report.processing_time_seconds)
        .filter(Report.status == "complete", Report.created_at >= since)
        .all()
    )
    values = sorted(float(r[0] or 0.0) for r in rows)
    if not values:
        return {"count": 0, "p50": None, "p95": None, "max": None}

    def percentile(fraction: float) -> float:
        # Nearest-rank. With a handful of samples the interpolated variants
        # invent a duration no request actually took.
        index = max(0, min(len(values) - 1, int(round(fraction * (len(values) - 1)))))
        return round(values[index], 3)

    return {
        "count": len(values),
        "p50": percentile(0.50),
        "p95": percentile(0.95),
        "max": round(values[-1], 3),
    }


def confidence_mix(session, *, days: int = DEFAULT_WINDOW_DAYS) -> dict:
    """
    How often the engine commits to a ruling versus declining to.

    The abstention rate is the number to watch. It going up means retrieval
    is finding less usable evidence, which is invisible in a verdict
    breakdown that treats UNVERIFIED as just another outcome.
    """
    since = _window_start(days)
    rows = (
        session.query(Report.confidence_band, func.count(Report.id))
        .filter(Report.status == "complete", Report.created_at >= since)
        .group_by(Report.confidence_band)
        .all()
    )
    bands = {band: int(count) for band, count in rows}

    decisive = (
        session.query(func.count(Report.id))
        .filter(Report.status == "complete", Report.created_at >= since)
        .filter(Report.verdict.notin_(ABSTAINING))
        .scalar()
    ) or 0
    total = sum(bands.values())

    return {
        "bands": bands,
        "total": total,
        "decisive": int(decisive),
        "abstentions": total - int(decisive),
        "abstention_rate": round((total - int(decisive)) / total, 3) if total else None,
    }


def _compute_overview(session, days: int) -> dict:
    return {
        "window_days": max(1, min(int(days), MAX_WINDOW_DAYS)),
        "volume": volume_over_time(session, days=days),
        "sources": source_leaderboard(session, days=days),
        "calibration": calibration(session, days=days),
        "latency": latency(session, days=days),
        "confidence": confidence_mix(session, days=days),
    }


def overview(session, *, days: int = DEFAULT_WINDOW_DAYS, fresh: bool = False) -> dict:
    """
    Everything the dashboard needs, in one round trip, cached briefly.

    The cache is here because measurement said indexes were the wrong tool.
    On a 60k-report corpus this aggregate took 443ms over 30 days and 790ms
    over a year, so the obvious move was to index `reports.created_at` and
    `evidence.source_domain`. Both were tried, and both made it **worse**:
    the domain index took the source panel from 113ms to 3119ms, because
    SQLite switched from a sequential scan with a hash group-by to an index
    scan with a random row lookup per row. Dropping the indexes restored it,
    repeatably, and `ANALYZE` helped one query while tripling another.

    So nothing is indexed for this, and the aggregate is cached instead. A
    panel labelled "trailing 30 days" does not need second-fresh numbers,
    and a short TTL bounds the cost at one scan per window per minute
    however many people are watching.

    `computed_at` goes in the payload so the dashboard can say how old the
    figures are rather than implying they are live.
    """
    window = max(1, min(int(days), MAX_WINDOW_DAYS))
    key = f"insights:overview:{window}"

    try:
        from truthshield.infra.cache import get_cache

        cache = get_cache()
        if not fresh:
            hit = cache.get(key)
            if hit is not None:
                return {**hit, "cached": True}

        payload = _compute_overview(session, window)
        payload["computed_at"] = datetime.now(timezone.utc).isoformat()
        cache.set(key, payload, ttl=OVERVIEW_CACHE_SECONDS)
        return {**payload, "cached": False}
    except Exception:
        # A cache outage degrades this to what it did before: slower, not
        # broken. The dashboard is never worth a 500.
        logger.debug("Insights cache unavailable", exc_info=True)
        payload = _compute_overview(session, window)
        payload["computed_at"] = datetime.now(timezone.utc).isoformat()
        return {**payload, "cached": False}
