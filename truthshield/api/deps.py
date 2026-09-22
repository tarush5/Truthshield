"""Request dependencies: identity, database session, rate-limit keys."""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from truthshield.infra.database import get_session
from truthshield.infra.models import User
from truthshield.services import auth
from truthshield.services.auth import Principal
from truthshield.settings import get_settings

logger = logging.getLogger(__name__)


def _bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1]


def current_principal(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    session: Session = Depends(get_session),
) -> Optional[Principal]:
    """
    Resolve the caller, or None.

    There is deliberately no anonymous-guest fallback. The previous version
    auto-provisioned a guest user whenever APP_ENV was "development" — the
    default value — which left the analysis API open on any deployment that
    had not explicitly set it.
    """
    token = _bearer(authorization)
    if token:
        payload = auth.decode_token(token)
        if payload:
            subject, email = payload.get("sub"), payload.get("email")
            if subject and email:
                try:
                    user_id = uuid.UUID(subject)
                except ValueError:
                    return None
                user = session.get(User, user_id)
                if user and user.is_active:
                    org = payload.get("org")
                    return Principal(
                        user_id=user.id,
                        email=user.email,
                        org_id=uuid.UUID(org) if org else None,
                    )

    if x_api_key:
        return auth.resolve_api_key(session, x_api_key)

    return None


def require_principal(principal: Optional[Principal] = Depends(current_principal)) -> Principal:
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return principal


def rate_limit_key(
    principal: Optional[Principal] = Depends(current_principal),
) -> str:
    """
    Limit per account where we know one, per address otherwise.

    Keying purely on IP punishes everyone behind a shared NAT for one abuser,
    and lets an attacker with many addresses past the limit entirely.
    """
    return f"user:{principal.user_id}" if principal else "anon"
