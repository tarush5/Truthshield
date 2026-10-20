"""
The investigation pipeline.

    VALIDATION → HASHING → EXTRACTION → CLASSIFICATION → FEATURE_EXTRACTION →
    MODEL_ANALYSIS → EVIDENCE_RETRIEVAL → CROSS_MODAL_ANALYSIS → RISK_ENGINE →
    EXPLANATION → REPORT → STORAGE

Every stage writes one `investigation_events` row when it ends -- completed,
skipped (with the reason), or failed -- so the timeline shows what happened,
including what did not. Only operational facts are recorded: which service
ran, how long it took, what it produced. Never model reasoning.

The runner owns its database session: it runs after the HTTP response in the
background executor, or in a Celery worker, where the request's session no
longer exists.
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Callable, List, Optional

from sqlalchemy.orm import Session

from truthshield.infra.models import (
    ClaimRecord, Investigation, InvestigationEvent, ModelPrediction as PredictionRow, RiskFactor,
)
from truthshield.investigations import explain
from truthshield.investigations.engines import analysis_engines, evidence_engines, media_engines
from truthshield.investigations.risk import RiskEngine
from truthshield.investigations.types import (
    STAGE_STATUS, EngineResult, EngineStatus, InvestigationContext, InvestigationStatus,
    InvestigationType, Stage,
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "2.0"

# Which families an engine can assess when it runs.
ENGINE_FAMILIES = {
    "text": {"nlp"}, "url": {"url"}, "evidence": {"evidence"},
    "document": {"document_media"}, "image": {"document_media"},
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class StageSkipped(Exception):
    """Raised inside a stage to record it as skipped, with the reason."""


class _Stage:
    def __init__(self):
        self.message: Optional[str] = None
        self.detail: dict = {}
        self.service = "pipeline"


class EventRecorder:
    def __init__(self, session: Session, investigation: Investigation):
        self.session = session
        self.investigation = investigation
        self.seq = 0

    @contextmanager
    def stage(self, stage: Stage, service: str = "pipeline"):
        inv = self.investigation
        inv.status = STAGE_STATUS[stage].value
        inv.current_stage = stage.value
        self.session.commit()

        record = _Stage()
        record.service = service
        started_at = _now()
        started = time.perf_counter()
        status = "completed"
        try:
            yield record
        except StageSkipped as skip:
            status = "skipped"
            record.message = str(skip)
        except Exception as exc:
            status = "failed"
            record.message = f"{type(exc).__name__} in {stage.value.lower()}"
            raise
        finally:
            self.seq += 1
            self.session.add(InvestigationEvent(
                investigation_id=inv.id,
                seq=self.seq,
                stage=stage.value,
                status=status,
                service=record.service,
                message=record.message,
                started_at=started_at,
                finished_at=_now(),
                duration_ms=int((time.perf_counter() - started) * 1000),
                detail=record.detail or None,
            ))
            self.session.commit()


class InvestigationRunner:
    def __init__(self, session_factory: Optional[Callable[[], Session]] = None):
        if session_factory is None:
            from truthshield.infra.database import SessionLocal
            session_factory = SessionLocal
        self._sessions = session_factory

    def run(self, investigation_id) -> None:
        session = self._sessions()
        try:
            inv = session.get(Investigation, uuid.UUID(str(investigation_id)))
            if inv is None:
                logger.warning("Investigation %s vanished before it ran", investigation_id)
                return
            if InvestigationStatus(inv.status).is_terminal:
                return
            self._run(session, inv)
        finally:
            session.close()

    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _clear_partial_attempt(session: Session, inv: Investigation) -> None:
        """
        Remove what an interrupted earlier attempt left behind.

        Celery acknowledges late, so a worker that dies mid-run has its task
        redelivered. Without this the second attempt wrote a second set of
        stage events (the counter restarts at 1) and, if the first had reached
        storage, duplicate risk factors, predictions and claim records.
        """
        if not session.query(InvestigationEvent).filter(InvestigationEvent.investigation_id == inv.id).count():
            return
        logger.warning("Investigation %s: discarding an interrupted earlier attempt", inv.public_id)
        for model in (InvestigationEvent, RiskFactor, PredictionRow, ClaimRecord):
            session.query(model).filter(model.investigation_id == inv.id).delete(synchronize_session=False)
        inv.result = None
        session.commit()
        session.refresh(inv)

    def _run(self, session: Session, inv: Investigation) -> None:
        self._clear_partial_attempt(session, inv)
        started = time.perf_counter()
        inv.started_at = _now()
        recorder = EventRecorder(session, inv)
        source = inv.inputs[0]

        try:
            self._execute(recorder, inv, source)
        except Exception as exc:
            logger.error("Investigation %s failed: %s", inv.public_id, exc, exc_info=True)
            session.rollback()
            inv = session.get(Investigation, inv.id)
            inv.status = InvestigationStatus.FAILED.value
            inv.current_stage = None
            inv.error = "The analysis could not be completed. The failure has been logged."
            inv.completed_at = _now()
            inv.processing_ms = int((time.perf_counter() - started) * 1000)
            session.commit()
            return

        inv.status = InvestigationStatus.COMPLETED.value
        inv.current_stage = None
        inv.completed_at = _now()
        inv.processing_ms = int((time.perf_counter() - started) * 1000)
        if inv.result is not None:
            inv.result = {**inv.result, "processing_ms": inv.processing_ms}
        session.commit()
        logger.info("Investigation %s completed in %sms (risk %s)",
                    inv.public_id, inv.processing_ms, inv.risk_score)

    def _execute(self, recorder: EventRecorder, inv: Investigation, source) -> None:
        from truthshield.settings import get_settings

        settings = get_settings()
        engines: List[EngineResult] = []

        kind = InvestigationType(inv.type)
        file_path = None

        with recorder.stage(Stage.VALIDATION, "gateway") as st:
            if kind.is_file:
                from truthshield.storage import get_storage

                path = get_storage().path_for(source.storage_key)
                if not path.exists():
                    raise FileNotFoundError("stored upload is missing")
                file_path = str(path)
                content = ""
                st.message = f"{source.mime_type} upload, {source.size_bytes:,} bytes, type verified at intake"
            else:
                content = source.content or ""
                if not content.strip():
                    raise ValueError("empty input")
                if len(content) > settings.MAX_TEXT_LENGTH:
                    raise ValueError("input exceeds the configured limit")
                st.message = f"{inv.type} input, {len(content)} characters, within limits"

        with recorder.stage(Stage.HASHING, "gateway") as st:
            if file_path:
                hasher = hashlib.sha256()
                with open(file_path, "rb") as fh:
                    for block in iter(lambda: fh.read(1024 * 1024), b""):
                        hasher.update(block)
                digest = hasher.hexdigest()
            else:
                digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
            if digest != source.sha256:
                # The stored input no longer matches what was hashed at intake.
                raise RuntimeError("input integrity check failed")
            st.message = f"SHA-256 verified: {digest[:16]}…"
            st.detail = {"sha256": digest}

        ctx = InvestigationContext(
            investigation_id=str(inv.id),
            type=kind,
            content=content,
            text=content,
            input_sha256=digest,
            allow_page_fetch=not inv.is_demo,
            file_path=file_path,
            mime_type=source.mime_type,
            filename=source.filename,
            owner_id=str(inv.user_id) if inv.user_id else None,
        )
        text_engine, url_engine = analysis_engines()

        with recorder.stage(Stage.EXTRACTION, text_engine.name) as st:
            parts = []
            for media in media_engines():
                media_result = media.run(ctx)
                if media_result.status is EngineStatus.NOT_APPLICABLE:
                    continue
                engines.append(media_result)
                st.service = media.name
                if media.name == "document":
                    self._duplicate_invoice(recorder.session, inv, media_result)
                parts.append(f"{media.name}: {len(ctx.text):,} characters extracted")
            text_result = text_engine.run(ctx)
            engines.append(text_result)
            ctx.artifacts.update(text_result.artifacts)
            if text_result.status is EngineStatus.NOT_APPLICABLE:
                if kind.is_file:
                    raise StageSkipped("; ".join(parts) or "No text could be extracted from the file.")
                raise StageSkipped("Input is a bare URL; no free text to extract from.")
            entities = text_result.artifacts.get("entities", {})
            parts.append(
                f"language {text_result.artifacts.get('language', {}).get('detected', '?')}; "
                f"{sum(len(v) for v in entities.values())} entities, "
                f"{len(text_result.artifacts.get('claims', []))} claims"
            )
            st.message = "; ".join(parts)
            inv.language = text_result.artifacts.get("language", {}).get("detected")

        with recorder.stage(Stage.CLASSIFICATION, text_engine.name) as st:
            if text_result.status is EngineStatus.NOT_APPLICABLE and kind is InvestigationType.URL:
                ctx.urls = [content.strip()]
                st.message = "Classified as URL"
            elif text_result.status is EngineStatus.NOT_APPLICABLE:
                st.message = f"Classified as {kind.value}; no text to classify"
            else:
                kinds = text_result.artifacts.get("input_kinds", [])
                cats = text_result.artifacts.get("fraud_categories", [])
                st.message = (
                    f"Input kinds: {', '.join(kinds) or 'TEXT'}"
                    + (f"; scam patterns: {', '.join(cats)}" if cats else "")
                )
                st.detail = {"input_kinds": kinds, "fraud_categories": cats}

        with recorder.stage(Stage.FEATURE_EXTRACTION, url_engine.name) as st:
            url_result = url_engine.run(ctx)
            engines.append(url_result)
            if url_result.status is EngineStatus.NOT_APPLICABLE:
                raise StageSkipped("No URLs in the input.")
            st.message = f"URL features computed for {url_result.features.get('urls_examined', 0)} link(s)"

        with recorder.stage(Stage.MODEL_ANALYSIS, "detectors") as st:
            predictions = [p for e in engines for p in e.predictions]
            signals = [s for e in engines for s in e.signals]
            st.message = (
                f"{len(predictions)} detector outputs, {len(signals)} signals. "
                "Phase 1 detectors are rule-based; no trained model is configured for this input type."
            )
            st.detail = {"detectors": sorted({p.model_name for p in predictions})}

        evidence_engine = evidence_engines()[0]
        with recorder.stage(Stage.EVIDENCE_RETRIEVAL, evidence_engine.name) as st:
            evidence_result = evidence_engine.run(ctx)
            engines.append(evidence_result)
            if evidence_result.status is EngineStatus.NOT_APPLICABLE:
                raise StageSkipped("No checkable factual claims were extracted.")
            if evidence_result.status is not EngineStatus.OK:
                raise StageSkipped(evidence_result.detail or "Evidence retrieval unavailable.")
            st.message = (
                f"{evidence_result.features.get('claims_checked', 0)} claim(s) checked, "
                f"{evidence_result.features.get('sources_retrieved', 0)} sources retrieved"
            )

        with recorder.stage(Stage.CROSS_MODAL_ANALYSIS, "risk") as st:
            contributing = [e.engine for e in engines if e.signals]
            if len(contributing) < 2:
                raise StageSkipped("Fewer than two engines produced signals; nothing to correlate.")
            st.message = f"Correlating signals from {', '.join(contributing)} in the risk engine"

        with recorder.stage(Stage.RISK_ENGINE, "risk") as st:
            assessed = set()
            for engine in engines:
                if engine.status is EngineStatus.OK:
                    assessed |= ENGINE_FAMILIES.get(engine.engine, set())
            risk_engine = RiskEngine()
            assessment = risk_engine.assess(
                [s for e in engines for s in e.signals], engines, assessed,
            )
            st.message = (
                f"Risk {assessment.score}/100 {assessment.level}, confidence "
                f"{assessment.confidence:.2f} ({assessment.config['version']})"
            )

        with recorder.stage(Stage.EXPLANATION, "explainer") as st:
            from truthshield.investigations.interpret import interpret

            classification, category = explain.classify(assessment, engines)
            uncertainties = explain.uncertainties(engines, assessment)
            actions = explain.recommended_actions(classification, category)
            evidence_result = next((e for e in engines if e.engine == "evidence"), None)
            checked_claims = (evidence_result.artifacts.get("claims") or []) if evidence_result else []
            llm_block, llm_record = interpret(assessment, checked_claims, uncertainties, ctx.input_sha256)
            extra_predictions = [llm_record] if llm_record is not None else []
            explanation = explain.explanation(assessment, classification, llm_block)
            st.message = (
                f"Classified as {classification.replace('_', ' ')}; "
                f"LLM interpretation: {llm_block['status'].replace('_', ' ')}"
            )

        with recorder.stage(Stage.REPORT, "report") as st:
            result = self._payload(inv, source, ctx, engines, assessment, classification,
                                   category, explanation, uncertainties, actions)
            st.message = f"Structured result assembled ({len(result['signals'])} signals)"

        with recorder.stage(Stage.STORAGE, "database") as st:
            session = recorder.session
            for contribution in assessment.contributions:
                session.add(RiskFactor(
                    investigation_id=inv.id, code=contribution.code, title=contribution.title[:200],
                    family=contribution.family, severity=contribution.severity,
                    provenance=contribution.provenance, engine=contribution.engine,
                    engine_version=contribution.engine_version, points=contribution.points,
                    confidence=contribution.confidence, evidence=contribution.evidence,
                    explanation=contribution.explanation,
                ))
            for p in [p for e in engines for p in e.predictions] + extra_predictions:
                session.add(PredictionRow(
                    investigation_id=inv.id, model_name=p.model_name, model_version=p.model_version,
                    model_kind=p.model_kind.value, task=p.task, input_sha256=p.input_sha256,
                    prediction=p.prediction, confidence=p.confidence,
                ))
            for claim in result["claims"]:
                session.add(ClaimRecord(
                    investigation_id=inv.id, claim_key=claim["id"], text=claim["text"],
                    assessment=claim.get("assessment") or "NOT_CHECKED",
                    confidence=claim.get("confidence"), source_count=len(claim.get("sources") or []),
                ))
            inv.result = result
            inv.risk_score = assessment.score
            inv.risk_level = assessment.level
            inv.confidence = assessment.confidence
            inv.confidence_band = assessment.confidence_band
            inv.classification = classification
            st.message = (
                f"{len(assessment.contributions)} risk factors and "
                f"{sum(len(e.predictions) for e in engines)} predictions stored"
            )

    @staticmethod
    def _duplicate_invoice(session, inv: Investigation, result: EngineResult) -> None:
        """Same invoice number, different file, same owner: a classic re-issue fraud."""
        from truthshield.fraud.contract import Severity
        from truthshield.investigations.types import Family, Provenance, Signal

        number = ((result.artifacts.get("document") or {}).get("fields") or {}).get("invoice_number")
        if not number or inv.user_id is None:
            return
        prior = (
            session.query(Investigation)
            .filter(Investigation.user_id == inv.user_id, Investigation.type == "document",
                    Investigation.id != inv.id, Investigation.input_sha256 != inv.input_sha256,
                    Investigation.status == "COMPLETED")
            .order_by(Investigation.created_at.desc()).limit(500).all()
        )
        matches = [p.public_id for p in prior
                   if (((p.result or {}).get("document") or {}).get("fields") or {}).get("invoice_number") == number]
        if matches:
            result.signals.append(Signal(
                code="duplicate_invoice_number", title="Invoice number seen on a different document",
                family=Family.DOCUMENT_MEDIA, severity=Severity.MEDIUM, provenance=Provenance.HEURISTIC,
                engine=result.engine, engine_version=result.version,
                explanation="A document with different content but the same invoice number was investigated "
                            "before. Re-issuing an invoice number with altered details is a common fraud pattern; "
                            "a corrected re-issue is the innocent explanation.",
                evidence=f"{number} also in {', '.join(matches[:3])}", confidence=0.6,
            ))

    def _payload(self, inv, source, ctx, engines, assessment, classification, category,
                 explanation, uncertainties, actions) -> dict:
        points = {c.code: c.points for c in assessment.contributions}
        signals = []
        for engine in engines:
            for s in engine.signals:
                item = s.model_dump(mode="json")
                item["points"] = points.get(s.code, 0)
                signals.append(item)
        signals.sort(key=lambda s: -s["points"])

        text_artifacts = next((e.artifacts for e in engines if e.engine == "text"), {})
        url_artifacts = next((e.artifacts for e in engines if e.engine == "url"), {})
        evidence = next((e for e in engines if e.engine == "evidence"), None)
        claims = (
            evidence.artifacts.get("claims")
            if evidence is not None and evidence.artifacts.get("claims") is not None
            else text_artifacts.get("claims", [])
        )

        features = {}
        for engine in engines:
            features.update(engine.features)

        return {
            "schema_version": SCHEMA_VERSION,
            "public_id": inv.public_id,
            "type": inv.type,
            "classification": classification,
            "fraud_category": category.value,
            "risk": assessment.model_dump(mode="json"),
            "signals": signals,
            "engines": [e.summary() for e in engines],
            "language": text_artifacts.get("language"),
            "entities": text_artifacts.get("entities", {}),
            "intents": text_artifacts.get("intents", []),
            "claims": claims,
            "url_intelligence": url_artifacts.get("urls", []),
            "prompt_injection": text_artifacts.get("prompt_injection", []),
            "document": next((e.artifacts.get("document") for e in engines if e.engine == "document"), None),
            "image": next((e.artifacts.get("image") for e in engines if e.engine == "image"), None),
            "features": features,
            "explanation": explanation,
            "uncertainties": uncertainties,
            "recommended_actions": actions,
            "input": {
                "type": inv.type,
                "sha256": source.sha256,
                "size_bytes": source.size_bytes,
                "redacted": source.redacted_content,
                "redactions": (source.meta or {}).get("redactions", []),
                "is_demo": inv.is_demo,
                "filename": source.filename,
                "mime_type": source.mime_type,
            },
        }
