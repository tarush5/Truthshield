"""Celery entry point for investigations, used when INVESTIGATION_EXECUTOR=celery."""

from __future__ import annotations

import logging

from celery.signals import worker_process_init

from truthshield.infra.celery_app import celery_app

logger = logging.getLogger(__name__)


@worker_process_init.connect
def _warm(**_kwargs) -> None:
    """Each worker process loads the engines once, not on its first task."""
    try:
        from truthshield.investigations.engines import warm_engines

        logger.info("Worker engines ready in %.0f ms", warm_engines())
    except Exception as exc:  # never stop a worker from starting
        logger.warning("Worker warm-up failed (non-fatal): %s", exc)


@celery_app.task(
    name="truthshield.investigations.run",
    acks_late=True,
    soft_time_limit=120,
    time_limit=180,
)
def run_investigation(investigation_id: str) -> str:
    from truthshield.investigations.pipeline import InvestigationRunner

    InvestigationRunner().run(investigation_id)
    return investigation_id
