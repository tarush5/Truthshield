"""
Audit logging.

The `audit_logs` table existed in 1.x and nothing ever wrote to it. Every
security-relevant action now goes through `record`, which never raises: an
audit write that fails is logged loudly, but must not undo the action the
user already completed.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from truthshield.infra.models import AuditLog

logger = logging.getLogger("truthshield.audit")


def record(
    session: Session,
    principal,
    action: str,
    resource: str,
    detail: Optional[dict] = None,
) -> None:
    from truthshield.api.middleware import current_request_id

    request_id = current_request_id()
    actor = getattr(principal, "user_id", None)
    org = getattr(principal, "org_id", None)

    logger.info("audit action=%s resource=%s actor=%s request_id=%s", action, resource, actor, request_id)
    if org is None:
        # audit_logs is workspace-scoped; an actor with no workspace is still
        # logged above, just not stored.
        return
    try:
        session.add(AuditLog(
            org_id=org,
            actor_id=actor,
            action=action,
            detail={"resource": resource, "request_id": request_id, **(detail or {})},
        ))
        session.commit()
    except Exception:
        session.rollback()
        logger.error("Audit write failed for %s on %s", action, resource, exc_info=True)
