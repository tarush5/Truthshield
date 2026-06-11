"""
TruthShield — Decision Pipeline
5-stage gate-based orchestrator with isolated contexts and async progress streaming.

Pipeline Stages:
  Stage 1: PREPROCESS  → Normalize input → produces ContentPacket
  Stage 2: DETECT      → Run all detectors → produces detector results
  Stage 3: VERIFY      → Claim extraction + evidence retrieval + verdicts
  Stage 4: AGGREGATE   → Cross-signal fusion via ResultAggregator
  Stage 5: RESPOND     → Counter-narratives + explanations (gated on trust_score < 75)

Each stage writes to PipelineContext — a mutable state bag that flows through the pipeline.
Gate conditions control whether downstream stages execute.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections import OrderedDict
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.models.schemas import (
    AIContentResult,
    AnalysisReport,
    ClaimVerdict,
    ContentPacket,
    ContentType,
    CounterNarrative,
    CredibilityScore,
    DeepfakeResult,
    Explanation,
    Inconsistency,
    Language,
    SocialSignal,
    TextClassificationResult,
    VoiceCloneResult,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# Pipeline Stage Enum
# ═══════════════════════════════════════════════════════════

class PipelineStage(str, Enum):
    """Ordered pipeline stages."""
    PREPROCESS = "preprocess"
    DETECT = "detect"
    VERIFY = "verify"
    AGGREGATE = "aggregate"
    RESPOND = "respond"


# ═══════════════════════════════════════════════════════════
# Stage Result
# ═══════════════════════════════════════════════════════════

class StageResult(BaseModel):
    """Output from a single pipeline stage."""
    stage: PipelineStage
    success: bool = True
    duration_ms: float = 0.0
    data: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════
# Pipeline Context
# ═══════════════════════════════════════════════════════════

class PipelineContext:
    """
    Mutable state bag that flows through the pipeline.
    Each stage reads from and writes to this context.
    No global state — everything lives here.
    """

    def __init__(
        self,
        text: Optional[str] = None,
        file_path: Optional[str] = None,
        url: Optional[str] = None,
        content_type: ContentType = ContentType.TEXT,
        lang: str = "en",
    ):
        # ── Input ────────────────────────────────────────────────
        self.input_text = text
        self.input_file_path = file_path
        self.input_url = url
        self.content_type = content_type
        self.lang = lang

        # ── Stage 1: Preprocess output ───────────────────────────
        self.packet: Optional[ContentPacket] = None

        # ── Stage 2: Detect output ───────────────────────────────
        self.text_classification: Optional[TextClassificationResult] = None
        self.ai_content_result: Optional[AIContentResult] = None
        self.deepfake_result: Optional[DeepfakeResult] = None
        self.voice_clone_result: Optional[VoiceCloneResult] = None

        # ── Stage 3: Verify output ───────────────────────────────
        self.claim_verdicts: List[ClaimVerdict] = []
        self.evidence_map: Dict[str, Any] = {}
        self.social_signals: List[SocialSignal] = []
        self.is_crisis: bool = False

        # ── Stage 4: Aggregate output ────────────────────────────
        self.trust_score: int = 50
        self.verdict: str = "UNVERIFIED"
        self.component_scores: Dict[str, float] = {}
        self.signal_correlations: Dict[str, float] = {}
        self.risk_factors: List[str] = []
        self.verdict_reasons: List[str] = []
        self.confidence_profile_data: Optional[Dict[str, Any]] = None

        # ── Stage 5: Respond output ──────────────────────────────
        self.explanation: Optional[Explanation] = None
        self.inconsistencies: List[Inconsistency] = []
        self.counter_narrative: Optional[CounterNarrative] = None

        # ── Pipeline metadata ────────────────────────────────────
        self.stage_results: List[StageResult] = []
        self.pipeline_start_time: float = 0.0


# Type alias for the async progress callback
ProgressCallback = Callable[
    [str, float, str, Optional[Dict[str, Any]]],
    Coroutine[Any, Any, None],
]


# ═══════════════════════════════════════════════════════════
# Decision Pipeline
# ═══════════════════════════════════════════════════════════

class DecisionPipeline:
    """
    5-stage gate-based analysis pipeline.

    Usage:
        pipeline = DecisionPipeline()
        report = await pipeline.execute(text="...", lang="en")

    With WebSocket streaming:
        report = await pipeline.execute(
            text="...", lang="en",
            progress_callback=tracker.send_progress
        )
    """

    # ── Class-level in-memory response cache (LRU, max 100 entries) ──────
    _cache: OrderedDict = OrderedDict()
    _CACHE_MAX_SIZE = 100
    _CACHE_TTL_SECONDS = 300  # 5 minutes

    def __init__(self):
        pass

    @classmethod
    def _cache_key(cls, text: str = None, url: str = None) -> str:
        """Generate a deterministic cache key from input."""
        raw = f"{text or ''}|{url or ''}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @classmethod
    def _cache_get(cls, key: str):
        """Get a cached report if it exists and hasn't expired."""
        if key in cls._cache:
            entry = cls._cache[key]
            if time.time() - entry["ts"] < cls._CACHE_TTL_SECONDS:
                cls._cache.move_to_end(key)  # LRU refresh
                logger.info(f"Cache HIT for key={key} (age={time.time()-entry['ts']:.1f}s)")
                return entry["report"]
            else:
                del cls._cache[key]  # Expired
        return None

    @classmethod
    def _cache_set(cls, key: str, report):
        """Store a report in cache with eviction."""
        cls._cache[key] = {"report": report, "ts": time.time()}
        if len(cls._cache) > cls._CACHE_MAX_SIZE:
            cls._cache.popitem(last=False)  # Evict oldest

    async def execute(
        self,
        text: Optional[str] = None,
        file_path: Optional[str] = None,
        url: Optional[str] = None,
        content_type: ContentType = ContentType.TEXT,
        lang: str = "en",
        progress_callback: Optional[ProgressCallback] = None,
    ) -> AnalysisReport:
        """
        Execute the full decision pipeline.

        Args:
            text: Input text to analyze
            file_path: Path to uploaded file (image/audio/video)
            url: URL to scrape and analyze
            content_type: Type of content
            lang: Language code (en/hi/ta)
            progress_callback: Optional async callback for streaming progress
                Signature: (stage, progress, message, partial_result) -> None

        Returns:
            AnalysisReport with all fields populated
        """
        ctx = PipelineContext(
            text=text,
            file_path=file_path,
            url=url,
            content_type=content_type,
            lang=lang,
        )
        ctx.pipeline_start_time = time.time()

        # ── Check in-memory cache ────────────────────────────────
        cache_key = self._cache_key(text=text, url=url)
        cached_report = self._cache_get(cache_key)
        if cached_report:
            if progress_callback:
                try:
                    await progress_callback("done", 1.0, "Analysis complete (cached)!", {
                        "report_id": cached_report.id,
                        "trust_score": cached_report.credibility.trust_score,
                        "verdict": cached_report.credibility.verdict,
                        "cached": True,
                    })
                except Exception:
                    pass
            return cached_report

        async def _progress(stage: str, progress: float, msg: str, data: Dict = None):
            if progress_callback:
                try:
                    await progress_callback(stage, progress, msg, data)
                except Exception as e:
                    logger.warning(f"Progress callback failed: {e}")
            # Small yield to allow message delivery
            await asyncio.sleep(0.05)

        try:
            # ── Stage 1: PREPROCESS ──────────────────────────────
            await _progress("preprocessing", 0.05, "Starting preprocessing...")
            stage1 = await self._stage_preprocess(ctx)
            ctx.stage_results.append(stage1)
            await _progress(
                "preprocessing", 0.20,
                f"Preprocessed. Language: {ctx.packet.lang.value if ctx.packet else 'unknown'}",
                {"language": ctx.packet.lang.value if ctx.packet else "unknown",
                 "text_length": len(ctx.packet.text or "") if ctx.packet else 0},
            )

            # Gate: if preprocessing failed, skip everything
            if not stage1.success or ctx.packet is None:
                return self._build_error_report(ctx, "Preprocessing failed")

            # ── Stage 2: DETECT ──────────────────────────────────
            await _progress("detecting", 0.25, "Running detection models...")
            stage2 = await self._stage_detect(ctx)
            ctx.stage_results.append(stage2)
            await _progress(
                "detecting", 0.50,
                f"Detection complete. Text: {ctx.text_classification.label if ctx.text_classification else 'N/A'}",
                {
                    "text_label": ctx.text_classification.label if ctx.text_classification else None,
                    "text_confidence": ctx.text_classification.confidence if ctx.text_classification else None,
                    "ai_probability": ctx.ai_content_result.ai_generated_probability if ctx.ai_content_result else None,
                },
            )

            # ── Stage 3: VERIFY ──────────────────────────────────
            # Gate: skip if no text to verify
            if ctx.packet.text:
                await _progress("verifying", 0.55, "Extracting claims...")
                stage3 = await self._stage_verify(ctx, _progress)
                ctx.stage_results.append(stage3)
                await _progress(
                    "verifying", 0.75,
                    f"Verification complete. {len(ctx.claim_verdicts)} claims evaluated.",
                    {"claims": [
                        {"claim": cv.claim.text, "verdict": cv.verdict.value,
                         "confidence": cv.confidence, "reasoning": cv.reasoning}
                        for cv in ctx.claim_verdicts
                    ]},
                )
            else:
                ctx.stage_results.append(StageResult(
                    stage=PipelineStage.VERIFY, success=True,
                    data={"skipped": True, "reason": "No text content to verify"},
                ))

            # ── Stage 4: AGGREGATE ───────────────────────────────
            await _progress("aggregating", 0.78, "Aggregating signals...")
            stage4 = await self._stage_aggregate(ctx)
            ctx.stage_results.append(stage4)
            await _progress(
                "aggregating", 0.85,
                f"Trust score: {ctx.trust_score}/100 — {ctx.verdict}",
                {
                    "trust_score": ctx.trust_score,
                    "verdict": ctx.verdict,
                    "confidence_band": ctx.confidence_profile_data.get("confidence_band") if ctx.confidence_profile_data else None,
                    "risk_factors": ctx.risk_factors,
                },
            )

            # ── Stage 5: RESPOND ─────────────────────────────────
            # Gate: only generate counter-response for flagged content
            if ctx.packet.text and ctx.trust_score < 75:
                await _progress("explaining", 0.87, "Generating counter-response...")
                stage5 = await self._stage_respond(ctx)
                ctx.stage_results.append(stage5)
                await _progress(
                    "explaining", 0.95,
                    "Counter-response generated",
                    {"explanation": {
                        "en": ctx.explanation.text_en if ctx.explanation else "",
                        "hi": ctx.explanation.text_hi if ctx.explanation else "",
                        "ta": ctx.explanation.text_ta if ctx.explanation else "",
                    }},
                )
            else:
                ctx.stage_results.append(StageResult(
                    stage=PipelineStage.RESPOND, success=True,
                    data={"skipped": True, "reason": "Content above trust threshold (≥75)"},
                ))

        except Exception as e:
            logger.error(f"Pipeline execution error: {e}", exc_info=True)
            return self._build_error_report(ctx, str(e))

        # ── Build final report ───────────────────────────────────
        report = self._build_report(ctx)

        # ── Store in cache ───────────────────────────────────────
        self._cache_set(cache_key, report)

        await _progress(
            "done", 1.0, "Analysis complete!",
            {
                "report_id": report.id,
                "trust_score": report.credibility.trust_score,
                "verdict": report.credibility.verdict,
                "confidence_band": report.credibility.confidence_band,
                "claims": [
                    {"claim": cv.claim.text, "verdict": cv.verdict.value,
                     "confidence": cv.confidence, "reasoning": cv.reasoning}
                    for cv in report.claims
                ],
                "explanation": {
                    "en": report.explanation.text_en if report.explanation else "",
                    "hi": report.explanation.text_hi if report.explanation else "",
                    "ta": report.explanation.text_ta if report.explanation else "",
                } if report.explanation else {},
                "signal_correlations": report.signal_correlations,
                "risk_factors": report.risk_factors,
            },
        )

        return report

    # ═══════════════════════════════════════════════════════════
    # Stage Implementations
    # ═══════════════════════════════════════════════════════════

    async def _stage_preprocess(self, ctx: PipelineContext) -> StageResult:
        """Stage 1: Preprocess input into ContentPacket."""
        start = time.time()
        errors = []

        try:
            if ctx.content_type == ContentType.TEXT and ctx.input_text:
                from backend.preprocessor.text_processor import TextProcessor
                processor = TextProcessor()
                ctx.packet = await asyncio.to_thread(processor.process, ctx.input_text, ctx.lang)

            elif ctx.content_type == ContentType.URL and ctx.input_url:
                from backend.preprocessor.url_scraper import URLScraper
                scraper = URLScraper()
                ctx.packet = await asyncio.to_thread(scraper.process, ctx.input_url, ctx.lang)

            elif ctx.content_type == ContentType.IMAGE and ctx.input_file_path:
                from backend.preprocessor.image_processor import ImageProcessor
                processor = ImageProcessor()
                ctx.packet = await asyncio.to_thread(processor.process, ctx.input_file_path, ctx.lang)

            elif ctx.content_type == ContentType.AUDIO and ctx.input_file_path:
                from backend.preprocessor.audio_processor import AudioProcessor
                processor = AudioProcessor()
                ctx.packet = await asyncio.to_thread(processor.process, ctx.input_file_path, ctx.lang)

            elif ctx.content_type == ContentType.VIDEO and ctx.input_file_path:
                from backend.preprocessor.video_processor import VideoProcessor
                processor = VideoProcessor()
                ctx.packet = await asyncio.to_thread(processor.process, ctx.input_file_path, ctx.lang)

            else:
                errors.append("No processable content provided")

        except Exception as e:
            logger.error(f"Preprocess stage error: {e}", exc_info=True)
            errors.append(str(e))

        duration = (time.time() - start) * 1000
        return StageResult(
            stage=PipelineStage.PREPROCESS,
            success=ctx.packet is not None,
            duration_ms=round(duration, 2),
            data={"content_type": ctx.content_type.value, "has_packet": ctx.packet is not None},
            errors=errors,
        )

    async def _stage_detect(self, ctx: PipelineContext) -> StageResult:
        """Stage 2: Run all applicable detectors."""
        start = time.time()
        errors = []

        try:
            tasks = []
            
            async def run_text_classifier():
                from backend.detectors.text_classifier import TextClassifier
                classifier = TextClassifier()
                ctx.text_classification = await asyncio.to_thread(
                    classifier.classify, ctx.packet.text, ctx.packet.lang.value
                )

            async def run_ai_content():
                from backend.detectors.ai_content_detector import AIContentDetector
                ai_detector = AIContentDetector()
                ctx.ai_content_result = await asyncio.to_thread(
                    ai_detector.analyze, ctx.packet.text, ctx.input_file_path
                )

            async def run_deepfake():
                from backend.detectors.deepfake_detector import DeepfakeDetector
                df_detector = DeepfakeDetector()
                ctx.deepfake_result = await asyncio.to_thread(
                    df_detector.analyze, ctx.packet.image_paths[:20]
                )

            async def run_voice_clone():
                from backend.detectors.voice_clone_detector import VoiceCloneDetector
                vc_detector = VoiceCloneDetector()
                ctx.voice_clone_result = await asyncio.to_thread(
                    vc_detector.analyze, ctx.packet.audio_path
                )

            if ctx.packet.text:
                tasks.append(run_text_classifier())
                tasks.append(run_ai_content())

            if ctx.packet.image_paths:
                tasks.append(run_deepfake())

            if ctx.packet.audio_path:
                tasks.append(run_voice_clone())

            if tasks:
                import asyncio
                await asyncio.gather(*tasks)

        except Exception as e:
            logger.error(f"Detection stage error: {e}", exc_info=True)
            errors.append(str(e))

        duration = (time.time() - start) * 1000
        return StageResult(
            stage=PipelineStage.DETECT,
            success=True,  # Detection is best-effort
            duration_ms=round(duration, 2),
            data={
                "text_label": ctx.text_classification.label if ctx.text_classification else None,
                "ai_prob": ctx.ai_content_result.ai_generated_probability if ctx.ai_content_result else None,
                "deepfake": ctx.deepfake_result.is_deepfake if ctx.deepfake_result else None,
                "voice_clone": ctx.voice_clone_result.is_cloned if ctx.voice_clone_result else None,
            },
            errors=errors,
        )

    async def _stage_verify(
        self, ctx: PipelineContext, progress_fn: Callable
    ) -> StageResult:
        """Stage 3: Claim extraction → evidence retrieval → verdict engine."""
        start = time.time()
        errors = []

        try:
            from backend.factcheck.claim_extractor import ClaimExtractor
            from backend.factcheck.evidence_retriever import EvidenceRetriever
            from backend.factcheck.verdict_engine import VerdictEngine
            from backend.factcheck.source_ranker import SourceRanker

            # Extract claims
            extractor = ClaimExtractor()
            import asyncio
            claims = await asyncio.to_thread(extractor.extract, ctx.packet.text, ctx.packet.lang.value)

            # ── Throttle claims to top 3 to prevent rate limiting ──
            if len(claims) > 3:
                logger.info(f"Throttling claims from {len(claims)} to 3 for speed")
                claims = claims[:3]

            await progress_fn(
                "verifying", 0.60,
                f"Extracted {len(claims)} verifiable claims",
                None,
            )

            if claims:
                retriever = EvidenceRetriever()
                ranker = SourceRanker()
                engine = VerdictEngine()

                import asyncio

                # Social signal enrichment
                try:
                    from backend.social_ingestion.social_signal_enricher import SocialSignalEnricher
                    enricher = SocialSignalEnricher()
                    fetch_url = ctx.input_url
                    if fetch_url:
                        ctx.social_signals = enricher.get_signals_for_url(fetch_url)
                        ctx.is_crisis = enricher.assess_crisis_potential(ctx.social_signals)
                except Exception as e:
                    logger.warning(f"Social enrichment skipped: {e}")

                # Retrieve and rank evidence per claim CONCURRENTLY
                evidence_map = {}
                
                async def process_claim(i, claim):
                    ev = await retriever.retrieve(claim)
                    ev = ranker.rank_evidence(ev)
                    ev = ranker.filter_disinfo(ev)
                    
                    progress = 0.60 + (i / len(claims)) * 0.12
                    await progress_fn(
                        "verifying", progress,
                        f"Evidence retrieved for claim {i + 1}/{len(claims)}",
                        None,
                    )
                    return claim.text, ev

                tasks = [process_claim(i, claim) for i, claim in enumerate(claims)]
                results = await asyncio.gather(*tasks)
                
                for text, ev in results:
                    evidence_map[text] = ev

                ctx.evidence_map = evidence_map

                # Evaluate claims via verdict engine concurrently
                async def eval_claim(c):
                    return await asyncio.to_thread(
                        engine.evaluate_claim, c, evidence_map.get(c.text, []), ctx.is_crisis
                    )
                
                eval_tasks = [eval_claim(c) for c in claims]
                ctx.claim_verdicts = list(await asyncio.gather(*eval_tasks))

        except Exception as e:
            logger.error(f"Verification stage error: {e}", exc_info=True)
            errors.append(str(e))

        duration = (time.time() - start) * 1000
        return StageResult(
            stage=PipelineStage.VERIFY,
            success=True,
            duration_ms=round(duration, 2),
            data={
                "claims_extracted": len(ctx.claim_verdicts),
                "is_crisis": ctx.is_crisis,
            },
            errors=errors,
        )

    async def _stage_aggregate(self, ctx: PipelineContext) -> StageResult:
        """Stage 4: Cross-signal fusion via ResultAggregator."""
        start = time.time()
        errors = []

        try:
            from backend.pipeline.result_aggregator import ResultAggregator

            aggregator = ResultAggregator()
            result = aggregator.aggregate(ctx)

            # Write aggregated results back to context
            ctx.trust_score = result.trust_score
            ctx.verdict = result.verdict
            ctx.component_scores = result.component_scores
            ctx.signal_correlations = result.signal_correlations
            ctx.risk_factors = result.risk_factors
            ctx.verdict_reasons = result.verdict_reasons

            if result.confidence_profile:
                ctx.confidence_profile_data = result.confidence_profile.model_dump()

        except Exception as e:
            logger.error(f"Aggregation stage error: {e}", exc_info=True)
            errors.append(str(e))

            # Fallback: use basic CredibilityScorer
            try:
                from backend.detectors.credibility_scorer import CredibilityScorer
                scorer = CredibilityScorer()
                cred = scorer.score(
                    text_result=ctx.text_classification,
                    deepfake_result=ctx.deepfake_result,
                    voice_result=ctx.voice_clone_result,
                    ai_content_result=ctx.ai_content_result,
                )
                ctx.trust_score = cred.trust_score
                ctx.verdict = cred.verdict
                ctx.component_scores = cred.component_scores
            except Exception as fallback_err:
                logger.error(f"Fallback scorer also failed: {fallback_err}")

        duration = (time.time() - start) * 1000
        return StageResult(
            stage=PipelineStage.AGGREGATE,
            success=len(errors) == 0,
            duration_ms=round(duration, 2),
            data={
                "trust_score": ctx.trust_score,
                "verdict": ctx.verdict,
                "correlations_found": len(ctx.signal_correlations),
                "risk_factors_count": len(ctx.risk_factors),
            },
            errors=errors,
        )

    async def _stage_respond(self, ctx: PipelineContext) -> StageResult:
        """Stage 5: Counter-response generation (gated on trust_score < 75)."""
        start = time.time()
        errors = []

        try:
            evidence_summary = ""
            if ctx.claim_verdicts:
                evidence_summary = "; ".join(
                    cv.reasoning for cv in ctx.claim_verdicts[:3] if cv.reasoning
                )

            async def do_explanation():
                try:
                    from backend.counter.multilingual_explainer import MultilingualExplainer
                    explainer = MultilingualExplainer()
                    ctx.explanation = await asyncio.to_thread(
                        explainer.explain, ctx.packet.text[:500], ctx.verdict, evidence_summary
                    )
                except Exception as e:
                    logger.warning(f"Explainer failed: {e}")
                    errors.append(f"Explanation generation failed: {e}")

            async def do_highlighting():
                try:
                    from backend.counter.inconsistency_highlighter import InconsistencyHighlighter
                    highlighter = InconsistencyHighlighter()
                    ctx.inconsistencies = await asyncio.to_thread(
                        highlighter.highlight_text, ctx.packet.text, ctx.verdict, evidence_summary
                    )
                except Exception as e:
                    logger.warning(f"Highlighter failed: {e}")
                    errors.append(f"Inconsistency highlighting failed: {e}")

            async def do_narrative():
                if ctx.claim_verdicts:
                    try:
                        from backend.counter.counter_narrative_generator import CounterNarrativeGenerator
                        generator = CounterNarrativeGenerator()
                        ctx.counter_narrative = await asyncio.to_thread(
                            generator.generate, ctx.packet.text, ctx.claim_verdicts
                        )
                    except Exception as e:
                        logger.warning(f"Counter-narrative failed: {e}")
                        errors.append(f"Counter-narrative generation failed: {e}")

            await asyncio.gather(do_explanation(), do_highlighting(), do_narrative())

        except Exception as e:
            logger.error(f"Response stage error: {e}", exc_info=True)
            errors.append(str(e))

        duration = (time.time() - start) * 1000
        return StageResult(
            stage=PipelineStage.RESPOND,
            success=True,  # Best-effort
            duration_ms=round(duration, 2),
            data={
                "has_explanation": ctx.explanation is not None,
                "inconsistency_count": len(ctx.inconsistencies),
                "has_counter_narrative": ctx.counter_narrative is not None,
            },
            errors=errors,
        )

    # ═══════════════════════════════════════════════════════════
    # Report Builders
    # ═══════════════════════════════════════════════════════════

    def _build_report(self, ctx: PipelineContext) -> AnalysisReport:
        """Assemble the final AnalysisReport from PipelineContext."""
        total_time = time.time() - ctx.pipeline_start_time

        return AnalysisReport(
            content_type=ctx.content_type,
            original_text=ctx.packet.text if ctx.packet else None,
            language=ctx.packet.lang if ctx.packet else Language(ctx.lang),
            credibility=CredibilityScore(
                trust_score=ctx.trust_score,
                verdict=ctx.verdict,
                component_scores=ctx.component_scores,
                confidence_band=ctx.confidence_profile_data.get("confidence_band", "MODERATE")
                if ctx.confidence_profile_data else "MODERATE",
            ),
            text_classification=ctx.text_classification,
            deepfake_result=ctx.deepfake_result,
            voice_clone_result=ctx.voice_clone_result,
            ai_content_result=ctx.ai_content_result,
            social_signals=ctx.social_signals,
            claims=ctx.claim_verdicts,
            inconsistencies=ctx.inconsistencies,
            counter_narrative=ctx.counter_narrative,
            explanation=ctx.explanation,
            source_url=ctx.input_url,
            is_crisis_content=ctx.is_crisis,
            processing_time_seconds=round(total_time, 2),
            # New pipeline fields
            pipeline_stages=[sr.model_dump() for sr in ctx.stage_results],
            signal_correlations=ctx.signal_correlations,
            risk_factors=ctx.risk_factors,
            confidence_profile=ctx.confidence_profile_data,
            verdict_reasons=ctx.verdict_reasons,
        )

    def _build_error_report(
        self, ctx: PipelineContext, error_msg: str
    ) -> AnalysisReport:
        """Build a report when the pipeline encounters a fatal error."""
        total_time = time.time() - ctx.pipeline_start_time

        return AnalysisReport(
            content_type=ctx.content_type,
            language=Language(ctx.lang),
            credibility=CredibilityScore(
                trust_score=50,
                verdict=f"ERROR — {error_msg}",
                component_scores={},
                confidence_band="VERY_LOW",
            ),
            processing_time_seconds=round(total_time, 2),
            pipeline_stages=[sr.model_dump() for sr in ctx.stage_results],
            risk_factors=[f"Pipeline error: {error_msg}"],
        )
