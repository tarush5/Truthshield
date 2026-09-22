"""
Authentication and authorization.

Every weakness the audit turned up in the previous implementation is closed
here by construction rather than by a later patch:

* Identity always comes from a **verified** token. Never from a field in the
  request body — an endpoint that trusted a caller-supplied `email` handed out
  sessions for arbitrary accounts.
* Only symmetric algorithms are accepted against a shared secret. Asymmetric
  tokens are rejected rather than decoded with signature verification off.
* There is no magic code, no dev bypass, no "guest" fallback. Those are the
  first things to survive into production.
* Secrets are compared in constant time and codes are single-use.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from jose import JWTError, jwt
from sqlalchemy.orm import Session

from truthshield.infra.models import APIKey, Organization, OrganizationMember, User
from truthshield.settings import get_settings

logger = logging.getLogger(__name__)

PBKDF2_ITERATIONS = 240_000      # OWASP guidance for SHA-256, 2024
OTP_TTL_SECONDS = 600
OTP_MAX_ATTEMPTS = 5


@dataclass(frozen=True)
class Principal:
    """Who is making this request."""

    user_id: uuid.UUID
    email: str
    org_id: Optional[uuid.UUID] = None
    via_api_key: bool = False


# ══════════════════════════════════════════════════════════════
# Passwords
# ══════════════════════════════════════════════════════════════

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: Optional[str]) -> bool:
    """
    Check a password.

    Always performs the full derivation, even when there is no stored hash, so
    that "this account does not exist" and "wrong password" take the same time
    and the endpoint cannot be used to enumerate registered addresses.
    """
    if not stored:
        hashlib.pbkdf2_hmac("sha256", password.encode(), b"dummy-salt", PBKDF2_ITERATIONS)
        return False
    try:
        algorithm, iterations, salt, expected = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations))
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


# ══════════════════════════════════════════════════════════════
# Tokens
# ══════════════════════════════════════════════════════════════

def issue_token(user: User, org_id: Optional[uuid.UUID] = None) -> Tuple[str, int]:
    settings = get_settings()
    expires_in = settings.JWT_EXPIRATION_MINUTES * 60
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "org": str(org_id) if org_id else None,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(seconds=expires_in),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expires_in


def decode_token(token: str) -> Optional[dict]:
    """
    Verify and decode a token, or return None.

    Both the local secret and the Supabase secret are tried, and both paths
    verify the signature. The algorithm is constrained to the symmetric family:
    accepting the token's own `alg` header would allow an attacker to pick one,
    and there is no key here capable of checking an asymmetric signature.
    """
    settings = get_settings()

    for secret in filter(None, (settings.JWT_SECRET_KEY, settings.SUPABASE_JWT_SECRET)):
        try:
            header = jwt.get_unverified_header(token)
            if not header.get("alg", "").startswith("HS"):
                logger.warning("Rejecting token with non-symmetric alg %r", header.get("alg"))
                return None
            return jwt.decode(
                token,
                secret,
                algorithms=["HS256", "HS384", "HS512"],
                options={"verify_aud": False},
            )
        except JWTError:
            continue
    return None


# ══════════════════════════════════════════════════════════════
# API keys
# ══════════════════════════════════════════════════════════════

def generate_api_key(session: Session, org_id: uuid.UUID, label: str, creator: uuid.UUID) -> Tuple[APIKey, str]:
    """
    Mint a key. The raw value is returned once and never stored.

    A plain SHA-256 is right here: the key is 128 bits of randomness, so it is
    not brute-forceable and needs no slow KDF (which would also make every
    authenticated request expensive).
    """
    raw = f"ts_{secrets.token_urlsafe(32)}"
    record = APIKey(
        org_id=org_id,
        created_by=creator,
        label=label,
        key_hash=hashlib.sha256(raw.encode()).hexdigest(),
        key_prefix=raw[:12],
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record, raw


def resolve_api_key(session: Session, raw: str) -> Optional[Principal]:
    digest = hashlib.sha256(raw.encode()).hexdigest()
    record = (
        session.query(APIKey)
        .filter(APIKey.key_hash == digest, APIKey.is_active.is_(True))
        .first()
    )
    if not record:
        return None

    user = session.get(User, record.created_by) if record.created_by else None
    if not user or not user.is_active:
        return None

    record.last_used_at = datetime.now(timezone.utc)
    session.commit()
    return Principal(user_id=user.id, email=user.email, org_id=record.org_id, via_api_key=True)


# ══════════════════════════════════════════════════════════════
# Workspace roles
# ══════════════════════════════════════════════════════════════

def role_in_org(session: Session, org_id: uuid.UUID, user_id: uuid.UUID) -> Optional[str]:
    member = (
        session.query(OrganizationMember)
        .filter(OrganizationMember.org_id == org_id, OrganizationMember.user_id == user_id)
        .first()
    )
    return member.role if member else None


def can_read_report(session: Session, report, principal: Optional[Principal]) -> bool:
    """
    Whether this principal may read this report.

    Unowned reports (anonymous submissions) stay readable by anyone holding
    the id, which is what share links rely on. Owned ones are restricted to
    the owner or a member of the workspace they were filed under — previously
    this endpoint took no identity at all.
    """
    if report.user_id is None and report.org_id is None:
        return True
    if principal is None:
        return False
    if report.user_id == principal.user_id:
        return True
    if report.org_id is not None:
        return role_in_org(session, report.org_id, principal.user_id) is not None
    return False


# ══════════════════════════════════════════════════════════════
# One-time codes
# ══════════════════════════════════════════════════════════════

class OTPStore:
    """
    Short-lived login codes, held in Redis so they work across workers.

    The previous store was a module-level dict: invisible to other processes,
    unbounded, never expiring, and with a hardcoded code that unlocked any
    account.
    """

    PREFIX = "otp:"

    def __init__(self):
        from truthshield.infra.cache import get_cache
        self._cache = get_cache()

    def issue(self, email: str) -> str:
        code = f"{secrets.randbelow(1_000_000):06d}"
        self._cache.set(
            f"{self.PREFIX}{email.lower()}",
            {"code": code, "issued_at": time.time(), "attempts": 0},
            ttl=OTP_TTL_SECONDS,
        )
        return code

    def verify(self, email: str, submitted: str) -> bool:
        key = f"{self.PREFIX}{email.lower()}"
        record = self._cache.get(key)
        if not record:
            return False

        if record.get("attempts", 0) >= OTP_MAX_ATTEMPTS:
            self._cache.delete(key)
            return False

        if time.time() - record.get("issued_at", 0) > OTP_TTL_SECONDS:
            self._cache.delete(key)
            return False

        if not hmac.compare_digest(str(record.get("code", "")), str(submitted)):
            record["attempts"] = record.get("attempts", 0) + 1
            self._cache.set(key, record, ttl=OTP_TTL_SECONDS)
            return False

        self._cache.delete(key)      # single use
        return True


def ensure_user(session: Session, email: str) -> User:
    user = session.query(User).filter(User.email == email).first()
    if user:
        return user
    user = User(email=email)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def ensure_personal_org(session: Session, user: User) -> Organization:
    """Every user gets a workspace, so reports always have somewhere to live."""
    existing = (
        session.query(Organization)
        .join(OrganizationMember, OrganizationMember.org_id == Organization.id)
        .filter(OrganizationMember.user_id == user.id)
        .first()
    )
    if existing:
        return existing

    org = Organization(name=f"{user.email.split('@')[0]}'s workspace", owner_id=user.id)
    session.add(org)
    session.flush()
    session.add(OrganizationMember(org_id=org.id, user_id=user.id, role="Admin"))
    session.commit()
    session.refresh(org)
    return org
