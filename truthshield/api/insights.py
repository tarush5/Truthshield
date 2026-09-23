"""
Analytics and claim-memory endpoints.

Kept out of `routes.py` because these read aggregate data across users,
which is a different access question from the per-report routes: everything
here is either organisation-scoped or deliberately non-identifying.

`/insights/*` never returns a claim's text, a user, or a report id that the
caller does not already own. The aggregates are counts, rates and domains.
`/claims/similar` does return prior claim text, so it requires a principal
and is the one route here that is authenticated rather than public.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from truthshield.api.deps import require_principal
from truthshield.domain import analytics
from truthshield.infra.database import get_session
from truthshield.services.auth import Principal

logger = logging.getLogger(__name__)

insights_router = APIRouter(prefix="/insights", tags=["insights"])
claims_router = APIRouter(prefix="/claims", tags=["claims"])

# The window every endpoint here accepts. Bounded in the query definition so
# a caller cannot ask for a decade and make the database sort the world.
_DAYS = Query(
    analytics.DEFAULT_WINDOW_DAYS,
    ge=1,
    le=analytics.MAX_WINDOW_DAYS,
    description="Size of the trailing window, in days.",
)


@insights_router.get("/overview")
def overview(
    days: int = _DAYS,
    fresh: bool = Query(False, description="Bypass the cache and recompute."),
    session: Session = Depends(get_session),
):
    """
    Everything the dashboard draws, in one request.

    One round trip rather than five: the panels share a time window, and
    fetching them separately lets them disagree about it when a request
    straddles midnight.

    Cached for a minute -- `computed_at` and `cached` are in the payload so
    the client can say how old the numbers are. `fresh=true` recomputes,
    which is what the dashboard's refresh control sends.
    """
    return analytics.overview(session, days=days, fresh=fresh)


@insights_router.get("/volume")
def volume(days: int = _DAYS, session: Session = Depends(get_session)):
    """Daily analysis counts, split by verdict. Buckets are dense."""
    return analytics.volume_over_time(session, days=days)


@insights_router.get("/sources")
def sources(
    days: int = _DAYS,
    limit: int = Query(15, ge=1, le=100),
    session: Session = Depends(get_session),
):
    """Most-cited domains, with credibility and stance split."""
    return analytics.source_leaderboard(session, days=days, limit=limit)


@insights_router.get("/calibration")
def calibration(days: int = _DAYS, session: Session = Depends(get_session)):
    """
    Reader agreement with each verdict class.

    Self-selected feedback, so every rate carries its denominator. See the
    docstring in `domain.analytics` before reading a number here as accuracy.
    """
    return analytics.calibration(session, days=days)


@insights_router.get("/performance")
def performance(days: int = _DAYS, session: Session = Depends(get_session)):
    """Latency percentiles and the commit-versus-abstain mix."""
    return {
        "latency": analytics.latency(session, days=days),
        "confidence": analytics.confidence_mix(session, days=days),
    }


@claims_router.get("/similar")
def similar(
    q: str = Query(..., min_length=8, max_length=500, description="Claim text."),
    limit: int = Query(5, ge=1, le=20),
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
):
    """
    Claims already adjudicated that resemble this one.

    Authenticated because it returns prior claim text. A near-duplicate hit
    is surfaced next to a fresh analysis, never in place of one -- see the
    module docstring in `domain.rag.store` for why a cached verdict would be
    the wrong thing to show.
    """
    from truthshield.domain.rag import get_claim_memory

    memory = get_claim_memory()
    memory.refresh(session)
    matches = memory.search(q, top_k=limit)

    return {
        "query": q,
        "matches": [m.as_dict() for m in matches],
        "indexed_claims": len(memory),
        # An operator reading this should be able to tell a lexical match
        # from a semantic one without inspecting the config.
        "matching": "embeddings" if memory.semantic else "lexical",
    }
