"""
TruthShield — Celery Background Tasks
Defines asynchronous task queues for processing heavy media files (audio/video).
"""
import os
import logging
import asyncio
from celery import Celery
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Initialize Celery app
celery_app = Celery(
    "truthshield",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task(name="tasks.analyze_content_task")
def analyze_content_task(
    report_id: str,
    text: str = None,
    file_path: str = None,
    url: str = None,
    content_type: str = "text",
    lang: str = "en",
    user_id: str = None,
    org_id: str = None
):
    """Celery background worker task to run the full analysis pipeline."""
    import uuid
    from backend.pipeline.decision_pipeline import DecisionPipeline
    from backend.models.db import SessionLocal, Report as ReportDB, EvidenceDB
    from backend.models.schemas import ContentType
    
    logger.info(f"Starting background analysis for report {report_id}...")
    
    pipeline = DecisionPipeline()
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    report = loop.run_until_complete(
        pipeline.execute(
            text=text,
            file_path=file_path,
            url=url,
            content_type=ContentType(content_type),
            lang=lang
        )
    )
    
    # Save the completed report to the database
    db = SessionLocal()
    try:
        db_report = db.query(ReportDB).filter(ReportDB.id == report_id).first()
        if db_report:
            db_report.verdict = report.credibility.verdict
            db_report.confidence = report.credibility.trust_score / 100.0
            if user_id:
                db_report.user_id = uuid.UUID(user_id)
            if org_id:
                db_report.org_id = uuid.UUID(org_id)
            
            # Save any retrieved evidence
            if report.claims:
                for claim_verdict in report.claims:
                    for ev in claim_verdict.evidence:
                        db_ev = EvidenceDB(
                            report_id=report_id,
                            source_url=ev.url,
                            source_name=ev.title,
                            credibility_score=ev.source_score,
                        )
                        db.add(db_ev)
            db.commit()
            
            # Log audit trail if org_id is provided
            if org_id:
                from backend.services.auth_service import AuthService
                AuthService.log_action(
                    db,
                    uuid.UUID(org_id),
                    uuid.UUID(user_id) if user_id else None,
                    "analyze_created",
                    {"report_id": report_id, "verdict": report.credibility.verdict, "content_type": content_type}
                )
            
            logger.info(f"Background analysis for report {report_id} completed successfully.")
    except Exception as e:
        logger.error(f"Failed to update report in Celery task: {e}")
    finally:
        db.close()
        
    return report_id
