"""
Celery application and tasks.

Async analysis is a real worker process here, not a FastAPI BackgroundTask.
The previous version queued to Celery and, when that failed, silently fell
back to running the job inside the web process via `loop.run_until_complete`
— which blocks a worker thread for the whole analysis and loses the job
entirely if the process restarts. If the broker is down now, the request is
rejected with 503 and the caller can retry.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from celery import Celery
from celery.signals import setup_logging

from truthshield.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

celery_app = Celery(
    "truthshield",
    broker=settings.celery_broker,
    backend=settings.celery_backend,
    include=["truthshield.infra.celery_app"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,

    # Acknowledge only after the task finishes, so a worker killed mid-job
    # returns the message to the queue instead of dropping the analysis.
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # One at a time: analysis is I/O-heavy with bursts of CPU, and a high
    # prefetch count leaves messages stranded behind a slow job.
    worker_prefetch_multiplier=1,

    task_time_limit=600,
    task_soft_time_limit=540,
    result_expires=86400,

    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_eager_propagates=True,
)


@setup_logging.connect
def _configure_logging(**_kwargs):
    """Keep the app's logging config rather than letting Celery replace it."""
    import logging.config
    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )


def broker_reachable() -> bool:
    """Whether the broker is accepting connections. Used by /health and /analyze."""
    if settings.CELERY_TASK_ALWAYS_EAGER:
        return True
    try:
        conn = celery_app.connection()
        conn.ensure_connection(max_retries=0, timeout=2)
        conn.release()
        return True
    except Exception as exc:
        logger.warning("Celery broker unreachable: %s", exc)
        return False


@celery_app.task(
    bind=True,
    name="truthshield.analyze",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=3,
)
def analyze_task(
    self,
    report_id: str,
    text: Optional[str] = None,
    url: Optional[str] = None,
    file_path: Optional[str] = None,
    content_type: str = "text",
    language: str = "en",
    user_id: Optional[str] = None,
    org_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run an analysis and persist it.

    Imports are deferred into the body so the worker does not pull the whole
    analysis stack — including torch — at module import time, which would slow
    every `celery inspect` and make the app import cost land on the web
    process too.
    """
    import asyncio

    from truthshield.services.analysis import AnalysisService
    from truthshield.infra.database import SessionLocal

    session = SessionLocal()
    try:
        service = AnalysisService(session)
        report = asyncio.run(
            service.analyze(
                report_id=report_id,
                text=text,
                url=url,
                file_path=file_path,
                content_type=content_type,
                language=language,
                user_id=user_id,
                org_id=org_id,
            )
        )
        return {
            "report_id": report.id,
            "verdict": report.verdict.value,
            "trust_score": report.trust_score,
        }
    except Exception as exc:
        logger.error("Analysis task failed for %s: %s", report_id, exc, exc_info=True)
        # Record the failure on the report so the UI can stop polling and say
        # what happened, rather than showing a job stuck at "running" forever.
        try:
            from truthshield.infra.models import Report
            row = session.get(Report, report_id)
            if row is not None:
                row.status = "failed"
                row.error = f"{type(exc).__name__}: {exc}"
                session.commit()
        except Exception:
            session.rollback()
        raise
    finally:
        session.close()
