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
    false,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

from truthshield.infra.database import GUID, Base, Embedding

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

    # Platform-wide permission level: USER | ANALYST | ADMIN. Distinct from
    # OrganizationMember.role, which scopes data sharing inside a workspace.
    role = Column(String(16), nullable=False, default="USER", server_default="USER")
    last_login_at = Column(DateTime(timezone=True), nullable=True)

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

    # Public sharing, opt-in per report and revocable.
    #
    # A report is private to its owner by default. Sharing mints an
    # unguessable token; revoking clears it, and the link stops working for
    # everyone immediately because the lookup is by this column. Nullable and
    # unique together mean any number of unshared reports coexist -- SQL
    # treats NULLs as distinct in a unique index.
    share_token = Column(String(64), nullable=True, unique=True, index=True)
    shared_at = Column(DateTime(timezone=True), nullable=True)

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


# ══════════════════════════════════════════════════════════════
# Sessions (2.0)
# ══════════════════════════════════════════════════════════════

class RefreshToken(Base, TimestampMixin):
    """
    A rotating refresh token, stored only as its SHA-256.

    Tokens issued by rotating one another share a `family_id`. Presenting a
    token that was already rotated or revoked revokes the whole family: that
    only happens when two parties hold the same token, and there is no way to
    tell which of them is the legitimate one, so both are signed out.
    """

    __tablename__ = "refresh_tokens"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    family_id = Column(GUID, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    replaced_by_id = Column(GUID, nullable=True)


# ══════════════════════════════════════════════════════════════
# Investigations (2.0)
# ══════════════════════════════════════════════════════════════

class Investigation(Base, TimestampMixin):
    """
    One submission and everything the platform concluded about it.

    Summary columns are duplicated out of `result` only because they are
    filtered, sorted and aggregated on; `result` is the source of truth for
    everything shown on the investigation page.
    """

    __tablename__ = "investigations"
    __table_args__ = (
        Index("ix_investigations_user_created", "user_id", "created_at"),
        # Administrators see every investigation: their dashboard window and
        # history sort have no user_id to lead with. The extra columns make it
        # covering for the dashboard, which then never touches the rows -- on
        # SQLite those carry the large `result` JSON in overflow pages.
        Index("ix_investigations_dashboard", "created_at", "status", "risk_level", "risk_score",
              "type", "classification", "processing_ms", "id"),
    )

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    public_id = Column(String(20), unique=True, nullable=False, index=True)
    user_id = Column(GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    org_id = Column(GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)

    type = Column(String(20), nullable=False, index=True)
    status = Column(String(24), nullable=False, default="QUEUED", index=True)
    # The stage running right now, for live progress. The permanent record of
    # every stage is investigation_events; this column only answers "where is it now".
    current_stage = Column(String(32), nullable=True)

    risk_score = Column(Integer, nullable=True)
    risk_level = Column(String(12), nullable=True, index=True)
    confidence = Column(Float, nullable=True)
    confidence_band = Column(String(12), nullable=True)
    classification = Column(String(48), nullable=True)
    language = Column(String(8), nullable=True)

    input_sha256 = Column(String(64), nullable=False, index=True)
    # Redacted preview. Lists and search never touch the original content.
    excerpt = Column(String(240), nullable=True)

    result = Column(JSONType, nullable=True)
    error = Column(Text, nullable=True)
    is_demo = Column(Boolean, nullable=False, default=False, server_default=false())

    processing_ms = Column(Integer, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    inputs = relationship("InvestigationInput", back_populates="investigation",
                          cascade="all, delete-orphan", passive_deletes=True)
    events = relationship("InvestigationEvent", back_populates="investigation",
                          cascade="all, delete-orphan", passive_deletes=True,
                          order_by="InvestigationEvent.seq")
    risk_factors = relationship("RiskFactor", back_populates="investigation",
                                cascade="all, delete-orphan", passive_deletes=True)
    predictions = relationship("ModelPrediction", back_populates="investigation",
                               cascade="all, delete-orphan", passive_deletes=True)
    reviews = relationship("InvestigationReview", back_populates="investigation",
                           cascade="all, delete-orphan", passive_deletes=True,
                           order_by="InvestigationReview.created_at")


class InvestigationReview(Base, TimestampMixin):
    """
    A person's view of an investigation: the submitter's feedback or appeal,
    and a reviewer's decision on it.

    Stored beside the deterministic result, never written into it: a
    reviewer's label does not change the score, level or claim assessments.
    The system's answer at the time is snapshotted here so accuracy can be
    measured against reviewed cases even after reanalysis or a config change.
    """

    __tablename__ = "investigation_reviews"
    __table_args__ = (Index("ix_investigation_reviews_queue", "status", "kind", "created_at"),)

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    investigation_id = Column(GUID, ForeignKey("investigations.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    author_id = Column(GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    kind = Column(String(16), nullable=False)          # feedback | appeal
    user_label = Column(String(16), nullable=False)    # fraud | legitimate | unsure
    comment = Column(Text, nullable=True)              # redacted before storage
    status = Column(String(16), nullable=False)        # recorded | open | resolved

    system_score = Column(Integer, nullable=True)
    system_level = Column(String(12), nullable=True)
    system_confidence = Column(Float, nullable=True)
    system_classification = Column(String(48), nullable=True)
    system_config_version = Column(String(32), nullable=True)

    reviewer_id = Column(GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewer_label = Column(String(16), nullable=True)  # fraud | legitimate | inconclusive
    reviewer_note = Column(Text, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    investigation = relationship("Investigation", back_populates="reviews")


class InvestigationInput(Base, TimestampMixin):
    """What was submitted, exactly as submitted. Written once, never updated."""

    __tablename__ = "investigation_inputs"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    investigation_id = Column(GUID, ForeignKey("investigations.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    kind = Column(String(20), nullable=False)
    content = Column(Text, nullable=True)
    redacted_content = Column(Text, nullable=True)
    sha256 = Column(String(64), nullable=False, index=True)
    size_bytes = Column(Integer, nullable=False, default=0)
    mime_type = Column(String(100), nullable=True)
    filename = Column(String(255), nullable=True)
    # Where an uploaded file lives in object storage (content-addressed by
    # SHA-256). Null for text inputs.
    storage_key = Column(String(255), nullable=True)
    meta = Column(JSONType, nullable=True)

    investigation = relationship("Investigation", back_populates="inputs")


class InvestigationEvent(Base, TimestampMixin):
    """One stage of the pipeline: the auditable timeline. Append-only."""

    __tablename__ = "investigation_events"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    investigation_id = Column(GUID, ForeignKey("investigations.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    seq = Column(Integer, nullable=False)
    stage = Column(String(32), nullable=False)
    status = Column(String(16), nullable=False)       # completed | skipped | failed
    service = Column(String(48), nullable=False)
    message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    detail = Column(JSONType, nullable=True)

    investigation = relationship("Investigation", back_populates="events")


class RiskFactor(Base, TimestampMixin):
    """One signal's share of the final risk score."""

    __tablename__ = "risk_factors"
    # Covering index for the dashboard's "most common risk factors" count.
    __table_args__ = (Index("ix_risk_factors_dashboard", "investigation_id", "points", "code", "title"),)

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    investigation_id = Column(GUID, ForeignKey("investigations.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    code = Column(String(64), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    family = Column(String(24), nullable=False)
    severity = Column(String(12), nullable=False)
    provenance = Column(String(24), nullable=False)
    engine = Column(String(48), nullable=False)
    engine_version = Column(String(24), nullable=False)
    points = Column(Float, nullable=False, default=0.0)
    confidence = Column(Float, nullable=True)
    evidence = Column(Text, nullable=True)
    explanation = Column(Text, nullable=True)

    investigation = relationship("Investigation", back_populates="risk_factors")


class ModelPrediction(Base, TimestampMixin):
    """
    A versioned engine output, keyed by input hash, so an investigation can be
    reproduced: same input, same engine version, same prediction.
    """

    __tablename__ = "model_predictions"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    investigation_id = Column(GUID, ForeignKey("investigations.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    model_name = Column(String(80), nullable=False, index=True)
    model_version = Column(String(24), nullable=False)
    model_kind = Column(String(16), nullable=False)    # heuristic | ml | retrieval | llm
    task = Column(String(48), nullable=False)
    input_sha256 = Column(String(64), nullable=False)
    prediction = Column(JSONType, nullable=True)
    confidence = Column(Float, nullable=True)

    investigation = relationship("Investigation", back_populates="predictions")


class InvestigationCounter(Base):
    """Per-year sequence behind TS-YYYY-NNNNNN public identifiers."""

    __tablename__ = "investigation_counters"

    year = Column(Integer, primary_key=True, autoincrement=False)
    value = Column(Integer, nullable=False, default=0)


# ══════════════════════════════════════════════════════════════
# Evidence store (2.0 Phase 2)
# ══════════════════════════════════════════════════════════════

class Source(Base, TimestampMixin):
    """
    A publisher, as a registry entry.

    `category` and `credibility` start from heuristics (domain suffix, the
    1.x credibility database) and are signals, never truth. An administrator
    can curate them; a curated entry is not overwritten by later heuristics.
    """

    __tablename__ = "sources"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    domain = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    category = Column(String(16), nullable=False, default="UNKNOWN", index=True)
    credibility = Column(Float, nullable=False, default=0.5)
    curated = Column(Boolean, nullable=False, default=False, server_default=false())
    notes = Column(Text, nullable=True)
    first_seen_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    last_seen_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    documents = relationship("EvidenceDocument", back_populates="source")


class EvidenceDocument(Base, TimestampMixin):
    """
    A retrieved or ingested document.

    The store is a cache of the web plus curated uploads: when the same URL is
    fetched again with different content its chunks are replaced. What an
    investigation *used* is snapshotted into that investigation's result, so
    past investigations are unaffected.
    """

    __tablename__ = "evidence_documents"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    source_id = Column(GUID, ForeignKey("sources.id", ondelete="SET NULL"), nullable=True, index=True)
    url = Column(Text, nullable=False)
    url_sha256 = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(Text, nullable=True)
    author = Column(String(255), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    retrieved_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    content_scope = Column(String(16), nullable=False, default="snippet")   # snippet | full_text | uploaded
    content_sha256 = Column(String(64), nullable=False)
    provider = Column(String(48), nullable=True)
    language = Column(String(8), nullable=True)
    meta = Column(JSONType, nullable=True)
    ingested_by = Column(GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    source = relationship("Source", back_populates="documents")
    chunks = relationship("EvidenceChunk", back_populates="document",
                          cascade="all, delete-orphan", passive_deletes=True,
                          order_by="EvidenceChunk.chunk_index")


class EvidenceChunk(Base, TimestampMixin):
    __tablename__ = "evidence_chunks"
    __table_args__ = (
        Index("ix_evidence_chunks_model", "embedding_model"),
    )

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    document_id = Column(GUID, ForeignKey("evidence_documents.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    char_start = Column(Integer, nullable=False, default=0)
    char_end = Column(Integer, nullable=False, default=0)
    embedding = Column(Embedding, nullable=True)
    # Vectors from different models are never compared; search filters on this.
    embedding_model = Column(String(80), nullable=False)

    document = relationship("EvidenceDocument", back_populates="chunks")


class ClaimRecord(Base, TimestampMixin):
    """A claim extracted in an investigation, normalised out of the result for search."""

    __tablename__ = "claims"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    investigation_id = Column(GUID, ForeignKey("investigations.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    claim_key = Column(String(8), nullable=False)          # C1, C2, ...
    text = Column(Text, nullable=False)
    assessment = Column(String(24), nullable=False, index=True)
    confidence = Column(Float, nullable=True)
    source_count = Column(Integer, nullable=False, default=0)
