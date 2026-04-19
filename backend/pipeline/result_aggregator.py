"""
TruthShield — Result Aggregator
Cross-signal fusion engine that correlates outputs from all pipeline stages.

Replaces the simple CredibilityScorer with multi-dimensional aggregation:
  • Signal correlation detection (agreement/contradiction between detectors)
  • Crisis amplification (stricter thresholds for viral content)
  • Claim verdict compounding (multiple FALSE claims → larger penalty)
  • Human-readable risk factor generation
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.models.schemas import (
    AIContentResult,
    CredibilityScore,
    DeepfakeResult,
    TextClassificationResult,
    VoiceCloneResult,
)
from backend.pipeline.confidence_scorer import ConfidenceProfile, ConfidenceScorer

if TYPE_CHECKING:
    from backend.pipeline.decision_pipeline import PipelineContext

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════

class AggregatedResult(BaseModel):
    """Comprehensive aggregation of all pipeline signals."""

    trust_score: int = 50  # 0–100
    verdict: str = "UNVERIFIED"
    component_scores: Dict[str, float] = Field(default_factory=dict)
    signal_correlations: Dict[str, float] = Field(default_factory=dict)
    risk_factors: List[str] = Field(default_factory=list)
    confidence_profile: Optional[ConfidenceProfile] = None


# ═══════════════════════════════════════════════════════════
# Result Aggregator
# ═══════════════════════════════════════════════════════════

class ResultAggregator:
    """
    Cross-signal fusion engine.

    Instead of simply averaging detector scores, this engine:
    1. Computes individual component scores
    2. Detects signal correlations (agreement/contradiction)
    3. Applies correlation adjustments to the trust score
    4. Factors in claim verdicts as compounding penalties
    5. Applies crisis amplification if content is viral
    6. Generates human-readable risk factors
    7. Delegates confidence scoring to ConfidenceScorer
    """

    def __init__(self):
        self._confidence_scorer = ConfidenceScorer()

    def aggregate(self, context: "PipelineContext") -> AggregatedResult:
        """
        Aggregate all pipeline signals into a unified result.

        Args:
            context: PipelineContext with all detector and verdict results

        Returns:
            AggregatedResult with trust_score, verdict, correlations, risk factors
        """
        component_scores: Dict[str, float] = {}
        signal_correlations: Dict[str, float] = {}
        risk_factors: List[str] = []

        # ── 1. Compute component scores ──────────────────────────
        base_score = self._score_text_classifier(
            context.text_classification, component_scores, risk_factors
        )
        deepfake_penalty = self._score_deepfake(
            context.deepfake_result, component_scores, risk_factors
        )
        voice_penalty = self._score_voice_clone(
            context.voice_clone_result, component_scores, risk_factors
        )
        ai_penalty = self._score_ai_content(
            context.ai_content_result, component_scores, risk_factors
        )

        # ── 2. Detect signal correlations ────────────────────────
        correlation_adjustment = self._compute_signal_correlations(
            context, signal_correlations, risk_factors
        )

        # ── 3. Claim verdict compounding ─────────────────────────
        verdict_penalty = self._compute_verdict_penalty(
            context, risk_factors
        )

        # ── 4. Compute raw trust score ───────────────────────────
        raw_score = base_score - deepfake_penalty - voice_penalty - ai_penalty
        raw_score += correlation_adjustment
        raw_score -= verdict_penalty

        # ── 5. Crisis amplification ──────────────────────────────
        if context.is_crisis:
            crisis_penalty = 0.08
            raw_score -= crisis_penalty
            risk_factors.append(
                "CRISIS FLAG: Content is spreading rapidly — higher scrutiny applied"
            )

        # ── 6. Clamp and convert ─────────────────────────────────
        trust_score = int(round(max(0.0, min(1.0, raw_score)) * 100))

        # ── 7. Determine verdict ─────────────────────────────────
        verdict = self._determine_verdict(trust_score, context)

        # ── 8. Confidence scoring ────────────────────────────────
        confidence_profile = self._confidence_scorer.compute(context)

        result = AggregatedResult(
            trust_score=trust_score,
            verdict=verdict,
            component_scores=component_scores,
            signal_correlations=signal_correlations,
            risk_factors=risk_factors,
            confidence_profile=confidence_profile,
        )

        logger.info(
            f"Aggregated result: trust_score={trust_score}, verdict={verdict}, "
            f"correlations={len(signal_correlations)}, risks={len(risk_factors)}, "
            f"confidence_band={confidence_profile.confidence_band}"
        )

        return result

    # ───────────────────────────────────────────────────────────
    # Component scoring
    # ───────────────────────────────────────────────────────────

    def _score_text_classifier(
        self,
        tc: Optional[TextClassificationResult],
        scores: Dict[str, float],
        risks: List[str],
    ) -> float:
        """Score the text classifier output. Returns base score (0–1)."""
        if tc is None or tc.label == "unknown":
            return 0.5  # Neutral baseline

        # Confidence floor: if confidence is too low, the classifier is guessing
        # Treat it as neutral to avoid anchoring the result on noise
        if tc.confidence < 0.40:
            risks.append(
                f"Text classifier confidence too low ({tc.confidence:.0%}) — treating as neutral"
            )
            scores["text_classifier"] = 50.0
            return 0.5  # Neutral baseline

        if tc.label == "real":
            base = 0.6 + tc.confidence * 0.4  # 0.6 → 1.0
        elif tc.label == "misleading":
            base = 0.5 + (0.5 - tc.confidence) * 0.2  # ~0.4 → 0.5
            risks.append(
                f"Text classifier flags content as MISLEADING ({tc.confidence:.0%} confidence)"
            )
        else:  # fake
            base = 0.4 - tc.confidence * 0.4  # 0.0 → 0.4
            risks.append(
                f"Text classifier flags content as FAKE ({tc.confidence:.0%} confidence)"
            )

        scores["text_classifier"] = round(base * 100, 1)
        return base

    def _score_deepfake(
        self,
        df: Optional[DeepfakeResult],
        scores: Dict[str, float],
        risks: List[str],
    ) -> float:
        """Score deepfake detector. Returns penalty (0–0.4)."""
        if df is None:
            return 0.0

        penalty = df.confidence * 0.4
        scores["deepfake_detector"] = round((1.0 - df.confidence) * 100, 1)

        if df.is_deepfake:
            risks.append(
                f"Deepfake detected in visual content ({df.confidence:.0%} confidence)"
            )
        if df.needs_human_review:
            risks.append("Visual content flagged for human review")

        return penalty

    def _score_voice_clone(
        self,
        vc: Optional[VoiceCloneResult],
        scores: Dict[str, float],
        risks: List[str],
    ) -> float:
        """Score voice clone detector. Returns penalty (0–0.3)."""
        if vc is None:
            return 0.0

        penalty = vc.anomaly_score * 0.3
        scores["voice_detector"] = round((1.0 - vc.anomaly_score) * 100, 1)

        if vc.is_cloned:
            risks.append(
                f"Voice cloning detected ({vc.confidence:.0%} confidence)"
            )

        return penalty

    def _score_ai_content(
        self,
        ai: Optional[AIContentResult],
        scores: Dict[str, float],
        risks: List[str],
    ) -> float:
        """Score AI content detector. Returns penalty (0–0.3)."""
        if ai is None:
            return 0.0

        prob = ai.ai_generated_probability
        penalty = prob * 0.3
        scores["ai_content_detector"] = round((1.0 - prob) * 100, 1)

        if prob > 0.7:
            risks.append(
                f"Content is likely AI-generated ({prob:.0%} probability)"
            )
        elif prob > 0.4:
            risks.append(
                f"Moderate AI-generation signal detected ({prob:.0%} probability)"
            )

        return penalty

    # ───────────────────────────────────────────────────────────
    # Signal correlation
    # ───────────────────────────────────────────────────────────

    def _compute_signal_correlations(
        self,
        context: "PipelineContext",
        correlations: Dict[str, float],
        risks: List[str],
    ) -> float:
        """
        Detect agreement/contradiction between detector signals.
        Returns an adjustment value (positive = boost trust, negative = reduce trust).
        """
        adjustment = 0.0

        tc = context.text_classification
        ai = context.ai_content_result

        # ── Text classifier + AI detector correlation ────────────
        if tc and tc.label != "unknown" and ai:
            text_is_fake = tc.label in ("fake", "misleading")
            ai_is_generated = ai.ai_generated_probability > 0.5

            if text_is_fake and ai_is_generated:
                # Strong agreement: both say problematic
                agreement = min(tc.confidence, ai.ai_generated_probability)
                correlations["text_ai_reinforcement"] = round(agreement, 3)
                adjustment -= agreement * 0.08  # Additional penalty for reinforced signal
                risks.append(
                    "CORRELATED: Text classifier and AI detector both flag this content"
                )
            elif not text_is_fake and not ai_is_generated:
                # Both say clean
                agreement = min(tc.confidence, 1.0 - ai.ai_generated_probability)
                correlations["text_ai_clean_agreement"] = round(agreement, 3)
                adjustment += agreement * 0.05  # Small trust boost
            else:
                # Contradiction
                correlations["text_ai_contradiction"] = round(
                    abs(tc.confidence - ai.ai_generated_probability), 3
                )
                risks.append(
                    "CONFLICTING: Text classifier and AI detector disagree"
                )

        # ── Deepfake + text correlation ──────────────────────────
        df = context.deepfake_result
        if df and df.is_deepfake and tc and tc.label == "fake":
            correlations["text_deepfake_reinforcement"] = round(
                min(tc.confidence, df.confidence), 3
            )
            adjustment -= 0.06
            risks.append(
                "CORRELATED: Both text and visual content flagged as manipulated"
            )

        # ── Claim verdicts + text classifier correlation ─────────
        if context.claim_verdicts and tc:
            false_claims = sum(
                1 for v in context.claim_verdicts if v.verdict.value == "FALSE"
            )
            total_claims = len(context.claim_verdicts)
            if total_claims > 0:
                false_ratio = false_claims / total_claims
                text_is_fake = tc.label in ("fake", "misleading")
                if false_ratio > 0.5 and text_is_fake:
                    correlations["text_verdict_reinforcement"] = round(false_ratio, 3)
                    adjustment -= false_ratio * 0.05
                elif false_ratio < 0.2 and not text_is_fake:
                    correlations["text_verdict_clean"] = round(1 - false_ratio, 3)
                    adjustment += 0.03

        return adjustment

    # ───────────────────────────────────────────────────────────
    # Claim verdict compounding
    # ───────────────────────────────────────────────────────────

    def _compute_verdict_penalty(
        self,
        context: "PipelineContext",
        risks: List[str],
    ) -> float:
        """
        Compound penalty from fact-check claim verdicts.
        Multiple FALSE claims produce a larger-than-linear penalty.
        """
        if not context.claim_verdicts:
            return 0.0

        false_count = 0
        misleading_count = 0
        total = len(context.claim_verdicts)

        for cv in context.claim_verdicts:
            if cv.verdict.value == "FALSE":
                false_count += 1
            elif cv.verdict.value == "MISLEADING":
                misleading_count += 1

        if false_count == 0 and misleading_count == 0:
            return 0.0

        # Linear + superlinear compounding for multiple false claims
        # 1 false = 0.08, 2 false = 0.20, 3 false = 0.36, etc.
        false_penalty = false_count * 0.08 + (false_count ** 2) * 0.02
        misleading_penalty = misleading_count * 0.04

        total_penalty = min(false_penalty + misleading_penalty, 0.5)

        if false_count > 0:
            risks.append(
                f"{false_count}/{total} claims verified as FALSE by fact-checkers"
            )
        if misleading_count > 0:
            risks.append(
                f"{misleading_count}/{total} claims flagged as MISLEADING"
            )

        return total_penalty

    # ───────────────────────────────────────────────────────────
    # Verdict determination
    # ───────────────────────────────────────────────────────────

    def _determine_verdict(
        self,
        trust_score: int,
        context: "PipelineContext",
    ) -> str:
        """Determine overall verdict from trust score and context."""
        # Crisis content uses tighter thresholds
        if context.is_crisis:
            if trust_score >= 80:
                return "LIKELY AUTHENTIC"
            elif trust_score >= 60:
                return "UNCERTAIN — VERIFY"
            elif trust_score >= 40:
                return "LIKELY MISLEADING"
            else:
                return "LIKELY FALSE"

        # Standard thresholds
        if trust_score >= 75:
            return "LIKELY AUTHENTIC"
        elif trust_score >= 55:
            return "UNCERTAIN — VERIFY"
        elif trust_score >= 35:
            return "LIKELY MISLEADING"
        else:
            return "LIKELY FALSE"
