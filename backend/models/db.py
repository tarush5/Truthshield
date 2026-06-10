"""
TruthShield — Database Config and ORM Models
"""
import uuid
import logging
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Float, DateTime, ForeignKey, Text, CHAR
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


class User(Base):
    __tablename__ = "users"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Report(Base):
    __tablename__ = "reports"
    id = Column(String, primary_key=True)  # Hex string UUID from schemas.py
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=True)
    content_type = Column(String, nullable=False)
    input_text = Column(Text, nullable=True)
    verdict = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    evidence = relationship("EvidenceDB", back_populates="report", cascade="all, delete-orphan")


class EvidenceDB(Base):
    __tablename__ = "evidence"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    report_id = Column(String, ForeignKey("reports.id"), nullable=False)
    source_url = Column(Text, nullable=False)
    source_name = Column(Text, nullable=True)
    credibility_score = Column(Float, nullable=False)

    report = relationship("Report", back_populates="evidence")


class FeedbackDB(Base):
    __tablename__ = "feedback"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    report_id = Column(String, ForeignKey("reports.id"), nullable=False)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=True)
    feedback = Column(Text, nullable=False)


class TrendingMisinfo(Base):
    __tablename__ = "trending_misinfo"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    claim = Column(Text, nullable=False)
    verdict = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    source_platform = Column(String, nullable=False)  # Twitter, Reddit, RSS
    virality_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


# Initialize SQLAlchemy Engine with connection checking & local SQLite fallback
try:
    engine = create_engine(settings.DATABASE_URL, connect_args={"connect_timeout": 2} if "postgresql" in settings.DATABASE_URL else {})
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
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully.")
    except Exception as e:
        logger.warning(f"Database initialization failed: {e}")


def get_db():
    """Dependency injection yielding database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
