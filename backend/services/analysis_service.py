"""
TruthShield — Multimodal Analysis Orchestration Service
"""
import os
import uuid
import logging
from typing import Optional
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models.schemas import ContentType, Language, AnalysisReport
from backend.models.db import Report as ReportDB, EvidenceDB
from backend.pipeline.decision_pipeline import DecisionPipeline

logger = logging.getLogger(__name__)
settings = get_settings()


class AnalysisService:
    """Service to coordinate the multimodal AI analysis pipeline and persist reports."""

    @staticmethod
    async def analyze(
        db: Session,
        text: Optional[str] = None,
        file_path: Optional[str] = None,
        url: Optional[str] = None,
        content_type: ContentType = ContentType.TEXT,
        lang: str = "en",
        user_id: Optional[uuid.UUID] = None,
        org_id: Optional[uuid.UUID] = None,
        progress_callback = None
    ) -> AnalysisReport:
        """Execute the analysis pipeline and persist results to the database."""
        pipeline = DecisionPipeline()
        report = await pipeline.execute(
            text=text,
            file_path=file_path,
            url=url,
            content_type=content_type,
            lang=lang,
            progress_callback=progress_callback,
        )

        # Persist to database
        logger.debug("AnalysisService.analyze called. user_id=%s, org_id=%s", user_id, org_id)
        try:
            import json
            logger.debug("Persisting report %s to database", report.id)
            db_report = ReportDB(
                id=report.id,
                user_id=user_id,
                org_id=org_id,
                content_type=report.content_type.value,
                language=report.language.value if hasattr(report, 'language') and report.language else lang,
                input_text=report.original_text,
                verdict=report.credibility.verdict,
                confidence=report.credibility.trust_score / 100.0,
                
                # Serialized fields
                claims_json=json.dumps([cv.model_dump() for cv in report.claims]) if report.claims else None,
                explanation_json=json.dumps(report.explanation.model_dump()) if report.explanation else None,
                counter_narrative_json=json.dumps(report.counter_narrative.model_dump()) if report.counter_narrative else None,
                inconsistencies_json=json.dumps([inc.model_dump() for inc in report.inconsistencies]) if report.inconsistencies else None,
                social_signals_json=json.dumps([sig.model_dump() for sig in report.social_signals]) if report.social_signals else None,
                risk_factors_json=json.dumps(report.risk_factors) if report.risk_factors else None,
                signal_correlations_json=json.dumps(report.signal_correlations) if report.signal_correlations else None,
                confidence_profile_json=json.dumps(report.confidence_profile) if report.confidence_profile else None,
                verdict_reasons_json=json.dumps(report.verdict_reasons) if report.verdict_reasons else None,
                processing_time_seconds=report.processing_time_seconds or 0.0,
            )
            db.add(db_report)

            # Persist search evidence
            if report.claims:
                for claim_verdict in report.claims:
                    for ev in claim_verdict.evidence:
                        db_ev = EvidenceDB(
                            report_id=report.id,
                            source_url=ev.url,
                            source_name=ev.title,
                            credibility_score=ev.source_score,
                        )
                        db.add(db_ev)

            db.commit()
            
            # Log audit event if workspace is present
            if org_id:
                from backend.services.auth_service import AuthService
                AuthService.log_action(
                    db,
                    org_id,
                    user_id,
                    "analyze_created",
                    {"report_id": report.id, "verdict": report.credibility.verdict, "content_type": content_type.value}
                )
            logger.info(f"Report {report.id} successfully saved to DB.")
        except Exception as e:
            logger.warning(f"Failed to persist report to DB: {e}")
            logger.exception("Traceback for report persistence failure")
            raise e

        return report
