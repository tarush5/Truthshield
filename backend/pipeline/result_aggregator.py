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
        Aggregate all pipeline signals into a unified result using weighted trust score:
        
        Trust Score = 0.50 × Fact Check + 0.20 × Source Credibility 
                    + 0.15 × ML Model + 0.15 × Gemini Reasoning

        Args:
            context: PipelineContext with all detector and verdict results

        Returns:
            AggregatedResult with trust_score, verdict, correlations, risk factors
        """
        component_scores: Dict[str, float] = {}
        signal_correlations: Dict[str, float] = {}
        risk_factors: List[str] = []

        # ── 1. Fact Check Score (50% weight) ─────────────────────
        fact_check_score = self._compute_fact_check_score(
            context, component_scores, risk_factors
        )

        # ── 2. Source Credibility Score (20% weight) ─────────────
        source_credibility_score = self._compute_source_credibility_score(
            context, component_scores, risk_factors
        )

        # ── 3. ML Model Score (15% weight) ───────────────────────
        ml_model_score = self._compute_ml_model_score(
            context, component_scores, risk_factors
        )

        # ── 4. Gemini/LLM Reasoning Score (15% weight) ──────────
        reasoning_score = self._compute_reasoning_score(
            context, component_scores, risk_factors
        )

        # ── 5. Weighted combination ──────────────────────────────
        weighted_score = (
            0.50 * fact_check_score
            + 0.20 * source_credibility_score
            + 0.15 * ml_model_score
            + 0.15 * reasoning_score
        )

        # ── 6. Signal correlations (adjustments) ─────────────────
        correlation_adjustment = self._compute_signal_correlations(
            context, signal_correlations, risk_factors
        )
        weighted_score += correlation_adjustment

        # ── 7. Crisis amplification ──────────────────────────────
        if context.is_crisis:
            weighted_score -= 0.08
            risk_factors.append(
                "CRISIS FLAG: Content is spreading rapidly — higher scrutiny applied"
            )

        # ── 8. Clamp and convert ─────────────────────────────────
        trust_score = int(round(max(0.0, min(1.0, weighted_score)) * 100))

        # ── 9. Compute support and refute scores for verdict determination ──
        support_scores = []
        refute_scores = []

        if not context.claim_verdicts:
            # Fallback based on ML Model score cleanliness
            if ml_model_score >= 0.70:
                support_score = ml_model_score
                refute_score = 0.0
            elif ml_model_score <= 0.40:
                support_score = 0.0
                refute_score = 1.0 - ml_model_score
            else:
                support_score = 0.0
                refute_score = 0.0
        else:
            for cv in context.claim_verdicts:
                v = cv.verdict.value.upper() if hasattr(cv.verdict, "value") else str(cv.verdict).upper()
                
                # Claim verdict signals
                if v == "TRUE":
                    cv_support = cv.confidence
                    cv_refute = 0.0
                elif v == "FALSE":
                    cv_support = 0.0
                    cv_refute = cv.confidence
                elif v == "MISLEADING":
                    cv_support = cv.confidence * 0.3
                    cv_refute = cv.confidence * 0.7
                else:  # UNVERIFIED
                    cv_support = 0.0
                    cv_refute = 0.0

                # Evidence stance signals
                supports_ev = [e for e in cv.evidence if getattr(e, "stance", "NEUTRAL") == "SUPPORTS"]
                refutes_ev = [e for e in cv.evidence if getattr(e, "stance", "NEUTRAL") == "REFUTES"]
                total_ev = len(cv.evidence)
                
                ev_support = len(supports_ev) / total_ev if total_ev > 0 else 0.0
                ev_refute = len(refutes_ev) / total_ev if total_ev > 0 else 0.0
                
                # Combine claim and evidence signals
                support_scores.append(cv_support * 0.6 + ev_support * 0.4)
                refute_scores.append(cv_refute * 0.6 + ev_refute * 0.4)
                
            support_score = sum(support_scores) / len(support_scores)
            refute_score = sum(refute_scores) / len(refute_scores)

        # ── 10. Expose multi-dimensional components for the frontend ──
        component_scores["fact_match"] = round(fact_check_score * 100, 1)
        
        all_ev = []
        stance_sig = 0
        for cv in context.claim_verdicts:
            for ev in cv.evidence:
                all_ev.append(ev)
                if getattr(ev, "stance", "NEUTRAL") in ("SUPPORTS", "REFUTES"):
                    stance_sig += 1
        
        stance_ratio = (stance_sig / len(all_ev)) if all_ev else 0.5
        avg_conf = sum(cv.confidence for cv in context.claim_verdicts) / len(context.claim_verdicts) if context.claim_verdicts else 0.5
        ev_strength_val = (avg_conf * 0.6 + stance_ratio * 0.4)
        source_count_factor = min(1.0, len(all_ev) / 4.0) if all_ev else 0.5
        ev_strength_val = ev_strength_val * 0.8 + source_count_factor * 0.2
        component_scores["evidence_strength"] = round(max(0.1, min(1.0, ev_strength_val)) * 100, 1)
        
        manip_risk = round((1.0 - ml_model_score) * 100, 1)
        component_scores["manipulation_risk"] = manip_risk
        component_scores["bias_risk"] = manip_risk

        # ── 11. Determine verdict ────────────────────────────────
        verdict = self._determine_verdict(trust_score, context, support_score, refute_score)

        # ── 12. Confidence scoring ───────────────────────────────
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
            f"weighted=[FC={fact_check_score:.2f}, SC={source_credibility_score:.2f}, "
            f"ML={ml_model_score:.2f}, LLM={reasoning_score:.2f}], "
            f"correlations={len(signal_correlations)}, risks={len(risk_factors)}"
        )

        return result

    # ───────────────────────────────────────────────────────────
    # Weighted component scoring
    # ───────────────────────────────────────────────────────────

    def _compute_fact_check_score(
        self,
        context: "PipelineContext",
        scores: Dict[str, float],
        risks: List[str],
    ) -> float:
        """
        Fact Check Score (50% weight).
        FALSE=0%, MISLEADING=40%, UNVERIFIED=70%, TRUE=100%.
        """
        if not context.claim_verdicts:
            scores["fact_check"] = 70.0  # Default: unverified
            return 0.70

        verdict_map = {
            "FALSE": 0.0,
            "MISLEADING": 0.40,
            "UNVERIFIED": 0.70,
            "TRUE": 1.0,
            "PARTIALLY_TRUE": 0.55,
        }

        claim_scores = []
        false_count = 0
        for cv in context.claim_verdicts:
            v = cv.verdict.value.upper()
            claim_score = verdict_map.get(v, 0.70)
            # Weight by confidence
            claim_scores.append(claim_score * cv.confidence + (1 - cv.confidence) * 0.70)
            if v == "FALSE":
                false_count += 1

        avg = sum(claim_scores) / len(claim_scores) if claim_scores else 0.70

        if false_count > 0:
            risks.append(
                f"{false_count}/{len(context.claim_verdicts)} claims verified as FALSE"
            )

        scores["fact_check"] = round(avg * 100, 1)
        return avg

    def _compute_source_credibility_score(
        self,
        context: "PipelineContext",
        scores: Dict[str, float],
        risks: List[str],
    ) -> float:
        """
        Source Credibility Score (20% weight).
        Average domain credibility of retrieved evidence.
        """
        if not context.evidence_map:
            scores["source_credibility"] = 50.0
            return 0.50

        all_scores = []
        for claim_text, evidence_list in context.evidence_map.items():
            for ev in evidence_list:
                if hasattr(ev, "source_score"):
                    all_scores.append(ev.source_score)

        if not all_scores:
            scores["source_credibility"] = 50.0
            return 0.50

        avg = sum(all_scores) / len(all_scores)
        scores["source_credibility"] = round(avg * 100, 1)

        if avg < 0.4:
            risks.append(f"Low source credibility ({avg:.0%} average)")

        return avg

    def _compute_ml_model_score(
        self,
        context: "PipelineContext",
        scores: Dict[str, float],
        risks: List[str],
    ) -> float:
        """
        ML Model Score (15% weight).
        Weighted average of text classifier, deepfake, voice clone, and AI detection.
        """
        ml_scores = []

        # Text classifier
        tc = context.text_classification
        if tc and tc.label != "unknown" and tc.confidence >= 0.40:
            if tc.label == "real":
                tc_score = 0.6 + tc.confidence * 0.4
            elif tc.label == "misleading":
                tc_score = 0.5 - tc.confidence * 0.2
                risks.append(f"Text classifier: MISLEADING ({tc.confidence:.0%})")
            else:  # fake
                tc_score = 0.4 - tc.confidence * 0.4
                risks.append(f"Text classifier: FAKE ({tc.confidence:.0%})")
            ml_scores.append(tc_score)
            scores["text_classifier"] = round(tc_score * 100, 1)

        # Deepfake
        df = context.deepfake_result
        if df:
            df_score = 1.0 - df.confidence
            ml_scores.append(df_score)
            scores["deepfake_detector"] = round(df_score * 100, 1)
            if df.is_deepfake:
                risks.append(f"Deepfake detected ({df.confidence:.0%})")

        # Voice clone
        vc = context.voice_clone_result
        if vc:
            vc_score = 1.0 - vc.anomaly_score
            ml_scores.append(vc_score)
            scores["voice_detector"] = round(vc_score * 100, 1)
            if vc.is_cloned:
                risks.append(f"Voice cloning detected ({vc.confidence:.0%})")

        # AI content
        ai = context.ai_content_result
        if ai:
            ai_score = 1.0 - ai.ai_generated_probability
            ml_scores.append(ai_score)
            scores["ai_content_detector"] = round(ai_score * 100, 1)
            if ai.ai_generated_probability > 0.7:
                risks.append(f"AI-generated content ({ai.ai_generated_probability:.0%})")

        if not ml_scores:
            scores["ml_model"] = 50.0
            return 0.50

        avg = sum(ml_scores) / len(ml_scores)
        scores["ml_model"] = round(avg * 100, 1)
        return avg

    def _compute_reasoning_score(
        self,
        context: "PipelineContext",
        scores: Dict[str, float],
        risks: List[str],
    ) -> float:
        """
        Gemini/LLM Reasoning Score (15% weight).
        Based on claim verdict confidence scores from LLM reasoning.
        """
        if not context.claim_verdicts:
            scores["reasoning"] = 50.0
            return 0.50

        confidences = [cv.confidence for cv in context.claim_verdicts if cv.confidence > 0]
        if not confidences:
            scores["reasoning"] = 50.0
            return 0.50

        # Higher confidence in verdicts = better reasoning quality
        avg_confidence = sum(confidences) / len(confidences)
        # Combine with verdict direction
        true_count = sum(1 for cv in context.claim_verdicts if cv.verdict.value.upper() == "TRUE")
        total = len(context.claim_verdicts)
        truth_ratio = true_count / total if total else 0.5

        reasoning_score = 0.5 * avg_confidence + 0.5 * truth_ratio
        scores["reasoning"] = round(reasoning_score * 100, 1)
        return reasoning_score

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
        support_score: float = 0.0,
        refute_score: float = 0.0,
    ) -> str:
        """Determine overall verdict from support and refute scores."""
        # If no support/refute scores are provided, derive them from trust_score
        if support_score == 0.0 and refute_score == 0.0:
            if trust_score >= 75:
                support_score = trust_score / 100.0
                refute_score = 0.0
            elif trust_score <= 35:
                support_score = 0.0
                refute_score = (100.0 - trust_score) / 100.0
            else:
                support_score = 0.0
                refute_score = 0.0

        if support_score >= 0.80:
            return "VERIFIED"
        elif support_score >= 0.55:
            return "LIKELY TRUE"
        elif refute_score >= 0.80:
            return "FALSE"
        elif refute_score >= 0.55:
            return "LIKELY FALSE"
        elif support_score >= 0.25 and refute_score >= 0.25:
            return "MIXED EVIDENCE"
        else:
            return "INSUFFICIENT EVIDENCE"
