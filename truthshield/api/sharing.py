"""
Public, revocable share links for a report.

A fact-check that cannot leave the account that ran it is half a product:
the point of checking a claim is usually to show someone else the answer.
Reports are private by default, and this is the deliberate, per-report,
revocable exception.

The security model, stated plainly:

* **Opt-in.** Nothing is public until the owner shares it. There is no
  setting that makes future reports public by default, because the failure
  mode of that setting is publishing someone's search history.

* **The token is the capability.** 32 bytes from `secrets`, URL-safe. It is
  guessed or it is not; there is no enumeration surface, because the token
  is the lookup key and report ids are never accepted on the public route.

* **Revocation is immediate and total.** The lookup is `WHERE share_token =
  ?`, so clearing the column stops every copy of the link at once. Re-sharing
  mints a *new* token rather than restoring the old one -- otherwise revoking
  and re-sharing would silently re-arm links the owner believed dead.

* **The public view is narrower than the owner's.** It carries the verdict,
  the evidence and the reasoning. It does not carry who ran it, when their
  account was created, or the report id that would let a caller try the
  authenticated routes.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from truthshield.api import schemas
from truthshield.api.deps import require_principal
from truthshield.infra.database import get_session
from truthshield.infra.models import Report
from truthshield.services.auth import Principal

logger = logging.getLogger(__name__)

sharing_router = APIRouter(tags=["sharing"])

# 32 bytes -> 43 URL-safe characters. Far past guessing, and still short
# enough to survive being pasted into a chat window unbroken.
TOKEN_BYTES = 32


def _owned_report(report_id: str, principal: Principal, session: Session) -> Report:
    """
    The caller's report, or 404.

    404 and not 403 on someone else's report: a 403 confirms the id exists,
    which turns this into an oracle for probing which reports are real.
    """
    report = session.query(Report).filter(Report.id == report_id).first()
    if report is None or str(report.user_id) != str(principal.user_id):
        raise HTTPException(status_code=404, detail="Report not found.")
    return report


@sharing_router.post("/reports/{report_id}/share", status_code=status.HTTP_201_CREATED)
def create_share_link(
    report_id: str,
    request: Request,
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
):
    """
    Make this report readable by anyone holding the link.

    Minting is idempotent per share: calling it twice on an already-shared
    report returns the existing token rather than rotating it, so a link the
    owner has already sent does not die because they pressed the button
    again.
    """
    report = _owned_report(report_id, principal, session)

    if not report.share_token:
        report.share_token = secrets.token_urlsafe(TOKEN_BYTES)
        report.shared_at = datetime.now(timezone.utc)
        session.commit()
        logger.info("Report %s shared by %s", report_id, principal.user_id)

    return {
        "token": report.share_token,
        "path": f"/shared/{report.share_token}",
        "shared_at": report.shared_at.isoformat() if report.shared_at else None,
    }


@sharing_router.delete("/reports/{report_id}/share", status_code=status.HTTP_204_NO_CONTENT)
def revoke_share_link(
    report_id: str,
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
):
    """
    Stop the link working, for everyone, now.

    Idempotent: revoking an unshared report succeeds. The caller's intent is
    "this must not be public", and that is already true.
    """
    report = _owned_report(report_id, principal, session)
    if report.share_token:
        report.share_token = None
        report.shared_at = None
        session.commit()
        logger.info("Share revoked for report %s by %s", report_id, principal.user_id)
    return None


@sharing_router.get("/shared/{token}", response_model=schemas.SharedReportOut)
def read_shared_report(token: str, session: Session = Depends(get_session)):
    """
    Read a shared report. No authentication.

    Looked up by token and never by id, so this route cannot be used to
    probe for reports that exist but were not shared.
    """
    # Bounded before it reaches the database: an unbounded path segment
    # becomes an unbounded query parameter.
    if not token or len(token) > 128:
        raise HTTPException(status_code=404, detail="This link is not valid.")

    report = session.query(Report).filter(Report.share_token == token).first()
    if report is None or report.status != "complete":
        # One message for "never existed", "revoked" and "still running".
        # Distinguishing them tells a stranger something about a report they
        # have no claim to.
        raise HTTPException(status_code=404, detail="This link is not valid.")

    from truthshield.services.analysis import AnalysisService

    return schemas.SharedReportOut.of(
        AnalysisService.rehydrate(report),
        shared_at=report.shared_at,
    )
