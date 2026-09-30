"""
Database engine and session management.

The previous version wrapped engine creation in a try/except that fell back to
a local SQLite file whenever Postgres was unreachable. That turns an outage
into silent data loss: the API keeps answering 200, reports keep being
"saved", and they land in a file nobody reads. Connection failures here are
allowed to propagate — a database that is down should look down.
"""

from __future__ import annotations

import logging
import uuid
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.types import CHAR, TypeDecorator

from truthshield.settings import get_settings

logger = logging.getLogger(__name__)

Base = declarative_base()


class GUID(TypeDecorator):
    """UUID column that is native on PostgreSQL and CHAR(36) elsewhere."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID
            return dialect.type_descriptor(UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(str(value))
        return value if dialect.name == "postgresql" else str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _build_engine() -> Engine:
    settings = get_settings()

    if settings.uses_sqlite:
        engine = create_engine(
            settings.DATABASE_URL,
            connect_args={"check_same_thread": False},
            echo=settings.DB_ECHO,
        )

        # SQLite ignores foreign keys unless asked. Without this, tests pass
        # against constraints that Postgres would enforce in production.
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_connection, _):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine

    return create_engine(
        settings.DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        # Recycles connections a proxy or Postgres may have dropped; without
        # it the first request after an idle period fails.
        pool_pre_ping=True,
        pool_recycle=1800,
        echo=settings.DB_ECHO,
    )


engine: Engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """
    FastAPI dependency yielding a session that is rolled back on error.

    The previous version's dependency only closed the session, so a handler
    that raised mid-transaction returned the connection to the pool with work
    still pending on it.
    """
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_connection() -> bool:
    """True when the database answers. Used by the readiness probe."""
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("Database unreachable: %s", exc)
        return False
