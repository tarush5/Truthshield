"""Celery entry point for investigations, used when INVESTIGATION_EXECUTOR=celery."""

from __future__ import annotations

from truthshield.infra.celery_app import celery_app


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
