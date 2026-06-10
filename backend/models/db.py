"""
TruthShield — Database Config and ORM Models
Multi-tenant architecture supporting workspaces, RBAC, API keys, audit logs, and pgvector embeddings.
"""
import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, String, Float, DateTime, ForeignKey, Text, CHAR, Boolean
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

Base = declarative_base()


class GUID(TypeDecorator):
    """
    Platform-independent GUID type.
    Uses PostgreSQL's UUID type, otherwise string CHAR(36).
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import UUID
            return dialect.type_descriptor(UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value
        else:
            return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                try:
                    return uuid.UUID(value)
                except ValueError:
                    return value
            return value


class VectorType(TypeDecorator):
    """
    Cross-platform Vector type.
    Maps to native pgvector 'Vector(384)' on PostgreSQL, and Text on SQLite.
    """
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            try:
                from pgvector.sqlalchemy import Vector
                return dialect.type_descriptor(Vector(384))
            except ImportError:
                return dialect.type_descriptor(Text)
        else:
            return dialect.type_descriptor(Text)

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return value
        else:
            import json
            return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return value
        else:
            import json
            try:
                return json.loads(value)
            except Exception:
                return value


class User(Base):
    __tablename__ = "users"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Organization(Base):
    __tablename__ = "organizations"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    org_id = Column(GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False, default="Member")  # Admin, Member, Viewer
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class APIKey(Base):
    __tablename__ = "api_keys"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    org_id = Column(GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    key_hash = Column(String, unique=True, nullable=False, index=True)
    label = Column(String, nullable=False)
    created_by = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    org_id = Column(GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String, nullable=False)  # analyze_created, api_key_created, member_invited
    details = Column(Text, nullable=True)  # JSON text
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
class Report(Base):
    __tablename__ = "reports"
    id = Column(String, primary_key=True)  # Hex string UUID from schemas.py
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    org_id = Column(GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    content_type = Column(String, nullable=False)
    language = Column(String, nullable=True, default="en")  # en, hi, ta
    input_text = Column(Text, nullable=True)
    verdict = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Serialized JSON fields to fully reconstruct AnalysisReport
    claims_json = Column(Text, nullable=True)
    explanation_json = Column(Text, nullable=True)
    counter_narrative_json = Column(Text, nullable=True)
    inconsistencies_json = Column(Text, nullable=True)
    social_signals_json = Column(Text, nullable=True)
    risk_factors_json = Column(Text, nullable=True)
    signal_correlations_json = Column(Text, nullable=True)
    confidence_profile_json = Column(Text, nullable=True)
    processing_time_seconds = Column(Float, nullable=True, default=0.0)

    evidence = relationship("EvidenceDB", back_populates="report", cascade="all, delete-orphan")


class EvidenceDB(Base):
    __tablename__ = "evidence"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    report_id = Column(String, ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    source_url = Column(Text, nullable=False)
    source_name = Column(Text, nullable=True)
    credibility_score = Column(Float, nullable=False)

    report = relationship("Report", back_populates="evidence")


class FeedbackDB(Base):
    __tablename__ = "feedback"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    report_id = Column(String, ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    feedback = Column(Text, nullable=False)


class TrendingMisinfo(Base):
    __tablename__ = "trending_misinfo"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    claim = Column(Text, nullable=False)
    verdict = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    source_platform = Column(String, nullable=False)  # Twitter, Reddit, RSS
    virality_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    text = Column(Text, nullable=False)
    metadata_json = Column(Text, nullable=True)  # JSON text metadata
    embedding = Column(VectorType, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# Initialize SQLAlchemy Engine with connection checking & local SQLite fallback
try:
    _engine_kwargs = {}
    if "postgresql" in settings.DATABASE_URL:
        _engine_kwargs = {
            "connect_args": {"connect_timeout": 2},
            "pool_size": 10,
            "max_overflow": 20,
            "pool_pre_ping": True,
        }
    else:
        _engine_kwargs = {"connect_args": {}}
    engine = create_engine(settings.DATABASE_URL, **_engine_kwargs)
    # Test connection
    with engine.connect() as conn:
        pass
    logger.info("Connected successfully to PostgreSQL database.")
except Exception as e:
    logger.warning(f"Failed to connect to PostgreSQL ({e}). Falling back to local SQLite database.")
    # Fallback to local SQLite file
    engine = create_engine("sqlite:///./truthshield_dev.db", connect_args={"check_same_thread": False})


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all tables in the database if they do not exist."""
    try:
        # If postgresql, ensure pgvector extension is created
        if "postgresql" in engine.url.drivername:
            with engine.connect() as conn:
                from sqlalchemy import text
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
                logger.info("pgvector extension initialized.")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully.")
        
        # Self-healing check: Ensure users table has password_hash column
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('users')]
        if 'password_hash' not in columns:
            logger.info("Adding password_hash column to users table...")
            with engine.connect() as conn:
                if "sqlite" in engine.url.drivername or "sqlite" in engine.url.scheme:
                    conn.execute(text("ALTER TABLE users ADD COLUMN password_hash TEXT"))
                else:
                    conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"))
                conn.commit()
                logger.info("password_hash column added successfully.")

        # Self-healing check: Ensure reports table has JSON columns
        reports_cols = [col['name'] for col in inspector.get_columns('reports')]
        json_cols = [
            ("claims_json", "TEXT"),
            ("explanation_json", "TEXT"),
            ("counter_narrative_json", "TEXT"),
            ("inconsistencies_json", "TEXT"),
            ("social_signals_json", "TEXT"),
            ("risk_factors_json", "TEXT"),
            ("signal_correlations_json", "TEXT"),
            ("confidence_profile_json", "TEXT"),
            ("processing_time_seconds", "REAL"),
        ]
        with engine.connect() as conn:
            for col_name, col_type in json_cols:
                if col_name not in reports_cols:
                    logger.info(f"Adding {col_name} column to reports table...")
                    conn.execute(text(f"ALTER TABLE reports ADD COLUMN {col_name} {col_type}"))
            conn.commit()
            logger.info("JSON columns added to reports table successfully.")
    except Exception as e:
        logger.warning(f"Database initialization failed: {e}")


def get_db():
    """Dependency injection yielding database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
