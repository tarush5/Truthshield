"""
TruthShield — Pipeline Confidence Scorer
Bayesian-inspired confidence scoring with uncertainty quantification.

Replaces naive weighted averaging with:
  • Base-rate prior (how common misinformation is in general)
  • Likelihood updates from each evidence signal
  • Inter-rater agreement across detectors and claim verdicts
  • Explicit uncertainty factor enumeration
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Dict, List, Optional

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from backend.pipeline.decision_pipeline import PipelineContext

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════

class ConfidenceProfile(BaseModel):
    """Full confidence breakdown for an analysis."""

    overall_confidence: float = 0.5
    confidence_band: str = "MODERATE"  # HIGH / MODERATE / LOW / VERY_LOW
    evidence_strength: float = 0.5
    source_agreement: float = 0.5
    detector_agreement: float = 0.5
    uncertainty_factors: List[str] = Field(default_factory=list)
    bayesian_prior: float = 0.5
    posterior: float = 0.5
    likelihood_contributions: Dict[str, float] = Field(default_factory=dict)


# ═══════════════════════════════════════════════════════════
# Confidence Scorer
# ═══════════════════════════════════════════════════════════

class ConfidenceScorer:
    """
    Bayesian-inspired confidence scoring engine.

    The scorer starts with a prior probability that content is misinformation
    (base rate ~0.30 in social media contexts), then updates this probability
    using likelihood ratios from each detector and claim verdict.

    The final confidence score reflects how certain we are about our verdict,
    not the verdict itself (that's the trust_score's job).
    """

    # Base rate: ~30% of viral social media content contains misinformation
    DEFAULT_PRIOR = 0.30

    # How much each signal type shifts the posterior
    SIGNAL_WEIGHTS = {
        "text_classifier": 0.30,
        "ai_detector": 0.20,
        "deepfake_detector": 0.20,
        "voice_detector": 0.10,
        "claim_verdicts": 0.20,
    }

    def compute(self, context: "PipelineContext") -> ConfidenceProfile:
        """
        Compute a full confidence profile from the pipeline context.

        Args:
            context: PipelineContext containing all detector and verdict results

        Returns:
            ConfidenceProfile with Bayesian posterior and uncertainty factors
        """
        uncertainty_factors: List[str] = []
        likelihood_contributions: Dict[str, float] = {}

        # ── 1. Start with prior ──────────────────────────────────
        prior = self.DEFAULT_PRIOR
        if context.is_crisis:
            prior = 0.45  # Higher prior during crisis/viral events
            likelihood_contributions["crisis_prior_boost"] = 0.45

        # ── 2. Collect likelihood ratios from each signal ────────
        likelihoods: List[float] = []

        # 2a. Text classifier signal
        text_lr = self._text_classifier_likelihood(context, uncertainty_factors)
        if text_lr is not None:
            likelihoods.append(text_lr)
            likelihood_contributions["text_classifier"] = round(text_lr, 4)

        # 2b. AI content detector signal
        ai_lr = self._ai_detector_likelihood(context, uncertainty_factors)
        if ai_lr is not None:
            likelihoods.append(ai_lr)
            likelihood_contributions["ai_detector"] = round(ai_lr, 4)

        # 2c. Deepfake detector signal
        df_lr = self._deepfake_likelihood(context, uncertainty_factors)
        if df_lr is not None:
            likelihoods.append(df_lr)
            likelihood_contributions["deepfake_detector"] = round(df_lr, 4)

        # 2d. Voice clone detector signal
        vc_lr = self._voice_clone_likelihood(context, uncertainty_factors)
        if vc_lr is not None:
            likelihoods.append(vc_lr)
            likelihood_contributions["voice_detector"] = round(vc_lr, 4)

        # 2e. Claim verdict signal
        cv_lr = self._claim_verdict_likelihood(context, uncertainty_factors)
        if cv_lr is not None:
            likelihoods.append(cv_lr)
            likelihood_contributions["claim_verdicts"] = round(cv_lr, 4)

        # ── 3. Bayesian update ───────────────────────────────────
        # P(misinfo | evidence) = P(E|misinfo) * P(misinfo) / P(E)
        # We use log-odds for numerical stability
        if likelihoods:
            log_prior_odds = math.log(prior / (1 - prior + 1e-10))
            log_lr_sum = sum(math.log(max(lr, 1e-10)) for lr in likelihoods)
            log_posterior_odds = log_prior_odds + log_lr_sum
            posterior = 1.0 / (1.0 + math.exp(-log_posterior_odds))
        else:
            posterior = prior
            uncertainty_factors.append("No detector signals available — using prior only")

        posterior = max(0.01, min(0.99, posterior))

        # ── 4. Evidence strength ─────────────────────────────────
        evidence_strength = self._compute_evidence_strength(context, uncertainty_factors)

        # ── 5. Inter-rater agreement ─────────────────────────────
        detector_agreement = self._compute_detector_agreement(context, uncertainty_factors)
        source_agreement = self._compute_source_agreement(context, uncertainty_factors)

        # ── 6. Overall confidence ────────────────────────────────
        # Confidence = how certain we are about whatever verdict we gave
        # High when: strong evidence, detectors agree, many sources
        # Low when: contradicting signals, sparse evidence, unknown sources
        overall_confidence = (
            0.35 * evidence_strength
            + 0.30 * detector_agreement
            + 0.20 * source_agreement
            + 0.15 * (1.0 - len(uncertainty_factors) / max(len(uncertainty_factors) + 5, 1))
        )
        overall_confidence = max(0.05, min(0.99, overall_confidence))

        # ── 7. Confidence band ───────────────────────────────────
        if overall_confidence >= 0.75:
            band = "HIGH"
        elif overall_confidence >= 0.50:
            band = "MODERATE"
        elif overall_confidence >= 0.25:
            band = "LOW"
        else:
            band = "VERY_LOW"

        profile = ConfidenceProfile(
            overall_confidence=round(overall_confidence, 4),
            confidence_band=band,
            evidence_strength=round(evidence_strength, 4),
            source_agreement=round(source_agreement, 4),
            detector_agreement=round(detector_agreement, 4),
            uncertainty_factors=uncertainty_factors,
            bayesian_prior=round(prior, 4),
            posterior=round(posterior, 4),
            likelihood_contributions=likelihood_contributions,
        )

        logger.info(
            f"Confidence profile: band={band}, overall={overall_confidence:.2f}, "
            f"posterior={posterior:.3f}, uncertainties={len(uncertainty_factors)}"
        )

        return profile

    # ───────────────────────────────────────────────────────────
    # Likelihood ratio helpers
    # ───────────────────────────────────────────────────────────

    def _text_classifier_likelihood(
        self, context: "PipelineContext", uncertainties: List[str]
    ) -> Optional[float]:
        """Likelihood ratio from text classifier."""
        tc = context.text_classification
        if tc is None or tc.label == "unknown":
            uncertainties.append("Text classifier unavailable or inconclusive")
            return None

        if tc.label == "fake":
            # P(classifier says fake | actually misinfo) / P(classifier says fake | legit)
            return 1.0 + tc.confidence * 3.0  # 1.0 to 4.0
        elif tc.label == "misleading":
            return 1.0 + tc.confidence * 1.5  # 1.0 to 2.5
        else:  # real
            return 1.0 / (1.0 + tc.confidence * 3.0)  # 0.25 to 1.0

    def _ai_detector_likelihood(
        self, context: "PipelineContext", uncertainties: List[str]
    ) -> Optional[float]:
        """Likelihood ratio from AI content detector."""
        ai = context.ai_content_result
        if ai is None:
            uncertainties.append("AI content detector not run")
            return None

        prob = ai.ai_generated_probability
        if prob > 0.7:
            return 1.5 + prob  # 2.2 to 2.5 — strong AI signal
        elif prob > 0.4:
            uncertainties.append(f"AI detection in ambiguous zone ({prob:.0%})")
            return 1.0 + prob * 0.5  # mild signal
        else:
            return 0.8  # slight counter-evidence

    def _deepfake_likelihood(
        self, context: "PipelineContext", uncertainties: List[str]
    ) -> Optional[float]:
        """Likelihood ratio from deepfake detector."""
        df = context.deepfake_result
        if df is None:
            return None  # Not applicable (no images)

        if df.is_deepfake:
            return 2.0 + df.confidence * 2.0  # 2.0 to 4.0
        elif df.needs_human_review:
            uncertainties.append("Deepfake detector flagged for human review")
            return 1.2
        else:
            return 0.7  # slight counter-evidence

    def _voice_clone_likelihood(
        self, context: "PipelineContext", uncertainties: List[str]
    ) -> Optional[float]:
        """Likelihood ratio from voice clone detector."""
        vc = context.voice_clone_result
        if vc is None:
            return None  # Not applicable (no audio)

        if vc.is_cloned:
            return 2.0 + vc.confidence * 2.0
        else:
            return 0.8

    def _claim_verdict_likelihood(
        self, context: "PipelineContext", uncertainties: List[str]
    ) -> Optional[float]:
        """Likelihood ratio from fact-check claim verdicts."""
        verdicts = context.claim_verdicts
        if not verdicts:
            uncertainties.append("No claims extracted for verification")
            return None

        false_count = sum(1 for v in verdicts if v.verdict.value == "FALSE")
        misleading_count = sum(1 for v in verdicts if v.verdict.value == "MISLEADING")
        true_count = sum(1 for v in verdicts if v.verdict.value == "TRUE")
        unverified_count = sum(1 for v in verdicts if v.verdict.value == "UNVERIFIED")
        total = len(verdicts)

        if unverified_count == total:
            uncertainties.append("All claims unverified — insufficient evidence")
            return 1.0  # neutral

        # Weighted signal
        signal = (
            false_count * 3.0
            + misleading_count * 1.5
            - true_count * 2.0
        ) / max(total, 1)

        # Convert to likelihood ratio (centered at 1.0)
        lr = math.exp(signal * 0.5)
        return max(0.1, min(10.0, lr))

    # ───────────────────────────────────────────────────────────
    # Agreement & strength helpers
    # ───────────────────────────────────────────────────────────

    def _compute_evidence_strength(
        self, context: "PipelineContext", uncertainties: List[str]
    ) -> float:
        """How strong is the evidence we found?"""
        total_evidence = 0
        high_quality_evidence = 0

        for cv in context.claim_verdicts:
            for ev in cv.evidence:
                total_evidence += 1
                if ev.source_score >= 0.7:
                    high_quality_evidence += 1

        if total_evidence == 0:
            uncertainties.append("No evidence retrieved from any source")
            return 0.1

        if total_evidence < 3:
            uncertainties.append(f"Limited evidence pool ({total_evidence} sources)")

        # Strength = ratio of high-quality sources, boosted by volume
        quality_ratio = high_quality_evidence / total_evidence
        volume_factor = min(total_evidence / 10.0, 1.0)  # saturates at 10
        return 0.3 * volume_factor + 0.7 * quality_ratio

    def _compute_detector_agreement(
        self, context: "PipelineContext", uncertainties: List[str]
    ) -> float:
        """How much do different detectors agree with each other?"""
        signals: List[float] = []

        # Convert each detector output to a 0–1 "misinformation probability"
        tc = context.text_classification
        if tc and tc.label != "unknown":
            if tc.label == "fake":
                signals.append(0.8 + tc.confidence * 0.2)
            elif tc.label == "misleading":
                signals.append(0.5 + tc.confidence * 0.15)
            else:
                signals.append(0.2 - tc.confidence * 0.15)

        ai = context.ai_content_result
        if ai:
            signals.append(ai.ai_generated_probability * 0.8)

        df = context.deepfake_result
        if df:
            signals.append(df.confidence if df.is_deepfake else 1.0 - df.confidence)

        vc = context.voice_clone_result
        if vc:
            signals.append(vc.anomaly_score)

        if len(signals) < 2:
            uncertainties.append("Too few detector signals for agreement analysis")
            return 0.5  # neutral

        # Agreement = 1 - normalized variance
        mean_signal = sum(signals) / len(signals)
        variance = sum((s - mean_signal) ** 2 for s in signals) / len(signals)
        # Max possible variance for [0,1] values is 0.25
        normalized_variance = min(variance / 0.25, 1.0)

        agreement = 1.0 - normalized_variance

        if agreement < 0.5:
            uncertainties.append("Detectors show significant disagreement")

        return agreement

    def _compute_source_agreement(
        self, context: "PipelineContext", uncertainties: List[str]
    ) -> float:
        """How much do evidence sources agree with each other?"""
        if not context.claim_verdicts:
            return 0.5

        verdict_values = [cv.verdict.value for cv in context.claim_verdicts]
        if not verdict_values:
            return 0.5

        # If all verdicts are the same → high agreement
        unique_verdicts = set(verdict_values)
        if len(unique_verdicts) == 1:
            return 0.95

        # Penalize for disagrement
        most_common_count = max(verdict_values.count(v) for v in unique_verdicts)
        agreement = most_common_count / len(verdict_values)

        if agreement < 0.6:
            uncertainties.append("Claim verdicts show mixed results")

        return agreement
