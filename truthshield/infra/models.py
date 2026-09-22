"""
ORM models.

Differences from the previous schema that are deliberate:

* Report payloads live in a JSON column rather than nine separate `*_json`
  TEXT columns that the application serialised by hand. The old shape needed a
  "self-healing" block at startup that ran ALTER TABLE for each column it
  found missing — migrations by side effect, with no record of what had been
  applied. Alembic owns the schema now.
* Every foreign key is declared, with an explicit ondelete. The old schema
  left orphaned evidence rows behind whenever a report was removed.
* Columns that are always filtered on are indexed.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

from truthshield.infra.database import GUID, Base

# JSONB on Postgres (indexable, binary); plain JSON elsewhere.
JSONType = JSON().with_variant(JSONB(), "postgresql")


def _utcnow() -> datetime:
    """Timezone-aware UTC. datetime.utcnow() is naive and deprecated."""
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    email = Column(String(320), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    memberships = relationship("OrganizationMember", back_populates="user", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="user")


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    owner_id = Column(GUID, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    members = relationship("OrganizationMember", back_populates="organization", cascade="all, delete-orphan")
    api_keys = relationship("APIKey", back_populates="organization", cascade="all, delete-orphan")


class OrganizationMember(Base, TimestampMixin):
    __tablename__ = "organization_members"
    __table_args__ = (
        # A user can hold exactly one role per workspace. Without this the old
        # invite flow could insert duplicate rows and role checks became
        # order-dependent.
        UniqueConstraint("org_id", "user_id", name="uq_org_member"),
    )

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    org_id = Column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(32), nullable=False, default="Member")   # Admin | Member | Viewer

    organization = relationship("Organization", back_populates="members")
    user = relationship("User", back_populates="memberships")


class APIKey(Base, TimestampMixin):
    __tablename__ = "api_keys"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    org_id = Column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by = Column(GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    label = Column(String(120), nullable=False)
    # SHA-256 of the key. The key itself is 128 bits of randomness, so a plain
    # digest is appropriate here — it is not a password and needs no KDF.
    key_hash = Column(String(64), unique=True, nullable=False, index=True)
    key_prefix = Column(String(16), nullable=False)   # shown in the UI for identification
    is_active = Column(Boolean, default=True, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    organization = relationship("Organization", back_populates="api_keys")


class Report(Base, TimestampMixin):
    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_user_created", "user_id", "created_at"),
        Index("ix_reports_org_created", "org_id", "created_at"),
    )

    id = Column(String(32), primary_key=True)     # uuid4().hex
    user_id = Column(GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    org_id = Column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)

    status = Column(String(20), nullable=False, default="complete", index=True)  # queued|running|complete|failed
    content_type = Column(String(20), nullable=False)
    language = Column(String(8), nullable=False, default="en")
    input_text = Column(Text, nullable=True)
    source_url = Column(Text, nullable=True)

    verdict = Column(String(32), nullable=False, default="UNVERIFIED", index=True)
    trust_score = Column(Integer, nullable=False, default=50)
    confidence_band = Column(String(16), nullable=False, default="MODERATE")

    # The whole AnalysisReport. One column instead of nine hand-serialised
    # ones; the summary fields above are duplicated out of it only because
    # they are filtered and aggregated on.
    payload = Column(JSONType, nullable=True)

    processing_time_seconds = Column(Float, nullable=False, default=0.0)
    error = Column(Text, nullable=True)

    user = relationship("User", back_populates="reports")
    evidence = relationship("Evidence", back_populates="report", cascade="all, delete-orphan")
    feedback = relationship("Feedback", back_populates="report", cascade="all, delete-orphan")


class Evidence(Base, TimestampMixin):
    __tablename__ = "evidence"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    report_id = Column(String(32), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True)
    url = Column(Text, nullable=False)
    title = Column(Text, nullable=True)
    snippet = Column(Text, nullable=True)
    source_domain = Column(String(255), nullable=True)
    source_score = Column(Float, nullable=False, default=0.5)
    stance = Column(String(16), nullable=False, default="NEUTRAL")

    report = relationship("Report", back_populates="evidence")


class Feedback(Base, TimestampMixin):
    __tablename__ = "feedback"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    report_id = Column(String(32), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user_verdict = Column(String(32), nullable=False)
    comment = Column(Text, nullable=True)

    report = relationship("Report", back_populates="feedback")


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_org_created", "org_id", "created_at"),)

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    org_id = Column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(64), nullable=False)
    detail = Column(JSONType, nullable=True)
