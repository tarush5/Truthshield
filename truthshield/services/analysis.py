"""
Analysis orchestration and persistence.

Sits between the HTTP layer and the pipeline: runs the analysis, stores the
result, and converts stored rows back into domain objects.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from truthshield.domain.types import (
    AnalysisReport, ConfidenceBand, ContentType, Language, TrustBreakdown, Verdict,
)
from truthshield.infra.models import Evidence as EvidenceRow, Report as ReportRow
from truthshield.services.auth import Principal
from truthshield.services.pipeline import AnalysisPipeline
from truthshield.settings import get_settings

logger = logging.getLogger(__name__)


class AnalysisService:
    def __init__(self, session: Session):
        self._session = session
        self._pipeline = AnalysisPipeline()
        self._settings = get_settings()

    # ──────────────────────────────────────────────────────────

    async def analyze(
        self,
        *,
        report_id: str,
        text: Optional[str] = None,
        url: Optional[str] = None,
        file_path: Optional[str] = None,
        content_type: str = "text",
        language: str = "en",
        user_id: Optional[str] = None,
        org_id: Optional[str] = None,
        progress=None,
    ) -> AnalysisReport:
        report = await self._pipeline.run(
            report_id=report_id,
            text=text,
            url=url,
            file_path=file_path,
            content_type=ContentType(content_type),
            language=Language(language),
            progress=progress,
        )
        self._persist(report, user_id, org_id)
        return report

    def enqueue(
        self,
        *,
        text: Optional[str],
        url: Optional[str],
        file_path: Optional[str],
        content_type: ContentType,
        language: Language,
        principal: Principal,
    ) -> str:
        """
        Hand the work to a Celery worker.

        If the broker is unreachable the request is rejected rather than
        quietly run inside the web process. The old in-process fallback
        blocked a request thread for the whole analysis and lost the job on
        restart, while still telling the caller it had been queued.
        """
        from fastapi import HTTPException
        from truthshield.infra.celery_app import analyze_task, broker_reachable

        if not broker_reachable():
            raise HTTPException(
                status_code=503,
                detail="The analysis queue is unavailable. Please retry shortly.",
            )

        report_id = uuid.uuid4().hex
        row = ReportRow(
            id=report_id,
            user_id=principal.user_id,
            org_id=principal.org_id,
            status="queued",
            content_type=content_type.value,
            language=language.value,
            input_text=(text or "")[:20_000] or None,
            source_url=url,
            verdict=Verdict.INSUFFICIENT_EVIDENCE.value,
            trust_score=50,
        )
        self._session.add(row)
        self._session.commit()

        analyze_task.delay(
            report_id=report_id,
            text=text,
            url=url,
            file_path=file_path,
            content_type=content_type.value,
            language=language.value,
            user_id=str(principal.user_id),
            org_id=str(principal.org_id) if principal.org_id else None,
        )
        return report_id

    # ──────────────────────────────────────────────────────────

    def _persist(self, report: AnalysisReport, user_id, org_id) -> None:
        try:
            row = self._session.get(ReportRow, report.id)
            if row is None:
                row = ReportRow(id=report.id)
                self._session.add(row)

            row.user_id = uuid.UUID(user_id) if user_id else None
            row.org_id = uuid.UUID(org_id) if org_id else None
            row.status = "complete"
            row.content_type = report.content_type.value
            row.language = report.language.value
            row.input_text = report.original_text
            row.source_url = report.source_url
            row.verdict = report.verdict.value
            row.trust_score = report.trust_score
            row.confidence_band = report.confidence_band.value
            row.processing_time_seconds = report.processing_time_seconds
            # One JSON column instead of nine hand-serialised TEXT fields.
            row.payload = report.model_dump(mode="json")

            # Replace rather than append, so re-running an analysis does not
            # accumulate duplicate evidence rows.
            self._session.query(EvidenceRow).filter(
                EvidenceRow.report_id == report.id
            ).delete(synchronize_session=False)

            for claim in report.claims:
                for item in claim.evidence:
                    self._session.add(EvidenceRow(
                        report_id=report.id,
                        url=item.url,
                        title=item.title,
                        snippet=item.snippet[:2000],
                        source_domain=item.source_domain,
                        source_score=item.source_score,
                        stance=item.stance.value,
                    ))

            self._session.commit()
        except Exception as exc:
            self._session.rollback()
            # Persistence failing must not lose the caller's result — they
            # still get the report in the response.
            logger.error("Could not persist report %s: %s", report.id, exc, exc_info=True)

    # ──────────────────────────────────────────────────────────

    @staticmethod
    def rehydrate(row: ReportRow) -> AnalysisReport:
        """Rebuild the domain object from a stored row."""
        if row.payload:
            try:
                return AnalysisReport.model_validate(row.payload)
            except Exception as exc:
                logger.warning("Stored payload for %s is unreadable: %s", row.id, exc)
        return AnalysisService.placeholder(row)

    @staticmethod
    def placeholder(row: ReportRow) -> AnalysisReport:
        """A minimal report for rows that are queued, running, or unreadable."""
        return AnalysisReport(
            id=row.id,
            content_type=ContentType(row.content_type),
            language=Language(row.language),
            original_text=row.input_text,
            source_url=row.source_url,
            verdict=Verdict(row.verdict),
            trust_score=row.trust_score,
            confidence_band=ConfidenceBand(row.confidence_band),
            breakdown=TrustBreakdown(),
            summary="Analysis in progress." if row.status in ("queued", "running") else "",
            processing_time_seconds=row.processing_time_seconds,
            created_at=row.created_at,
        )
