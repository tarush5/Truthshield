"""
Analysis pipeline.

Four stages, each of which may degrade without taking the analysis down:

    ingest   → normalize whatever was submitted into a ContentPacket
    detect   → run manipulation detectors (they report whether they ran)
    verify   → extract claims, retrieve evidence, decide each claim
    score    → fuse into a verdict, or decline to

The pipeline never invents a result. If verification finds nothing, the scorer
returns INSUFFICIENT EVIDENCE and the report says which checks were skipped
and why.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Awaitable, Callable, List, Optional

from truthshield.domain.scoring.aggregator import TrustScorer
from truthshield.domain.types import (
    AnalysisReport, Claim, ClaimVerdict, ContentPacket, ContentType,
    DetectorResult, Language, Verdict,
)
from truthshield.domain.verdict import adapters
from truthshield.settings import get_settings

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, float, str], Awaitable[None]]


class AnalysisPipeline:
    def __init__(self):
        self._settings = get_settings()
        self._scorer = TrustScorer()

    async def run(
        self,
        *,
        report_id: Optional[str] = None,
        text: Optional[str] = None,
        url: Optional[str] = None,
        file_path: Optional[str] = None,
        content_type: ContentType = ContentType.TEXT,
        language: Language = Language.EN,
        progress: Optional[ProgressCallback] = None,
    ) -> AnalysisReport:
        started = time.perf_counter()
        report_id = report_id or uuid.uuid4().hex

        async def emit(stage: str, pct: float, message: str) -> None:
            if progress:
                try:
                    await progress(stage, pct, message)
                except Exception as exc:
                    # A disconnected websocket must not fail the analysis.
                    logger.debug("Progress callback failed: %s", exc)

        try:
            await emit("ingest", 0.05, "Reading submission")
            packet = await self._ingest(text, url, file_path, content_type, language)

            await emit("detect", 0.25, "Checking for manipulation")
            detectors = await asyncio.to_thread(self._detect, packet)

            await emit("verify", 0.45, "Finding and weighing evidence")
            claim_verdicts = await self._verify(packet, emit)

            await emit("score", 0.90, "Weighing it up")
            scored = self._scorer.score(packet, claim_verdicts, detectors)

            report = AnalysisReport(
                id=report_id,
                content_type=packet.content_type,
                language=packet.language,
                original_text=(packet.text or "")[: self._settings.MAX_TEXT_LENGTH] or None,
                source_url=packet.source_url,
                verdict=scored.verdict,
                trust_score=scored.trust_score,
                confidence_band=scored.confidence_band,
                breakdown=scored.breakdown,
                claims=claim_verdicts,
                detectors=detectors,
                summary=self._summary(scored.verdict, claim_verdicts),
                reasons=scored.reasons,
                limitations=scored.limitations,
                processing_time_seconds=round(time.perf_counter() - started, 3),
            )
            await emit("done", 1.0, "Analysis complete")
            return report

        except Exception as exc:
            logger.error("Pipeline failed for %s: %s", report_id, exc, exc_info=True)
            await emit("error", 1.0, str(exc))
            return AnalysisReport(
                id=report_id,
                content_type=content_type,
                language=language,
                original_text=text,
                source_url=url,
                verdict=Verdict.INSUFFICIENT_EVIDENCE,
                trust_score=50,
                summary="This submission could not be analyzed.",
                limitations=[f"Analysis failed: {type(exc).__name__}: {exc}"],
                processing_time_seconds=round(time.perf_counter() - started, 3),
            )

    # ──────────────────────────────────────────────────────────

    async def _ingest(self, text, url, file_path, content_type, language) -> ContentPacket:
        from truthshield.services.ingest import build_packet
        return await asyncio.to_thread(
            build_packet, text, url, file_path, content_type, language
        )

    def _detect(self, packet: ContentPacket) -> List[DetectorResult]:
        from truthshield.detectors.registry import run_all
        return run_all(packet)

    async def _verify(self, packet: ContentPacket, emit) -> List[ClaimVerdict]:
        if not packet.has_text:
            return []

        from truthshield.domain.evidence.ranker import SourceRanker
        from truthshield.domain.verdict.claim_extractor import ClaimExtractor
        from truthshield.domain.verdict.engine import VerdictEngine
        from truthshield.infra.evidence.retriever import EvidenceRetriever

        extractor = ClaimExtractor()
        claims = await asyncio.to_thread(extractor.extract, packet.text, packet.language.value)
        if not claims:
            return []

        # Bounded: each claim is an independent fan-out across every evidence
        # source, so an unbounded list turns one submission into dozens of
        # outbound requests.
        claims = claims[: self._settings.MAX_CLAIMS_PER_SUBMISSION]
        await emit("verify", 0.55, f"Checking {len(claims)} claim{'s' if len(claims) != 1 else ''}")

        retriever = EvidenceRetriever()
        ranker = SourceRanker()
        engine = VerdictEngine()

        async def check(claim):
            evidence = await retriever.retrieve(claim)
            evidence = ranker.filter_disinfo(ranker.rank_evidence(evidence))
            return await asyncio.to_thread(engine.evaluate_claim, claim, evidence, False)

        results = await asyncio.gather(*(check(c) for c in claims), return_exceptions=True)

        verdicts = []
        for claim, result in zip(claims, results):
            if isinstance(result, Exception):
                logger.warning("Claim check failed for %r: %s", claim.text[:60], result)
                continue
            verdicts.append(adapters.from_legacy_claim_verdict(result))
        return verdicts

    def _summary(self, verdict: Verdict, claim_verdicts: List[ClaimVerdict]) -> str:
        if not claim_verdicts:
            return "No checkable claim was found, so nothing could be verified."
        lead = claim_verdicts[0]
        return lead.reasoning or f"Assessed as {verdict.value.lower()}."
