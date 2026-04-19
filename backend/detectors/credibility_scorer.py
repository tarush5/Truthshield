"""
TruthShield — Credibility Scorer
Weighted fusion of all detector outputs into a single trust score.
"""

import logging
from typing import Optional

from backend.config import CREDIBILITY_WEIGHTS
from backend.models.schemas import (
    AIContentResult,
    CredibilityScore,
    DeepfakeResult,
    TextClassificationResult,
    VoiceCloneResult,
)

logger = logging.getLogger(__name__)


class CredibilityScorer:
    """
    Aggregate detector outputs into a unified trust score (0-100).
    
    Weights:
        text     = 0.35
        deepfake = 0.25  
        voice    = 0.20
        ai_content = 0.20
    """

    def __init__(self):
        self.weights = CREDIBILITY_WEIGHTS

    def score(
        self,
        text_result: Optional[TextClassificationResult] = None,
        deepfake_result: Optional[DeepfakeResult] = None,
        voice_result: Optional[VoiceCloneResult] = None,
        ai_content_result: Optional[AIContentResult] = None,
    ) -> CredibilityScore:
        """
        Compute weighted credibility score from detector outputs.

        Args:
            text_result: Text classification result
            deepfake_result: Deepfake detection result
            voice_result: Voice clone detection result
            ai_content_result: AI content detection result

        Returns:
            CredibilityScore with trust_score (0-100), verdict, and component scores
        """
        component_scores = {}
        
        # ── 1. Base Score (Semantic Truth) ─────────────────────────
        base_score = 0.5
        if text_result and text_result.label != "unknown":
            if text_result.label == "real":
                # 0.6 to 1.0
                base_score = 0.6 + text_result.confidence * 0.4
            elif text_result.label == "misleading":
                # 0.4 to 0.6
                base_score = 0.5 + (0.5 - text_result.confidence) * 0.2
            else:  # fake
                # 0.0 to 0.4
                base_score = 0.4 - text_result.confidence * 0.4
            
            component_scores["text"] = round(base_score * 100, 1)

        final_score = base_score

        # ── 2. Penalties (Manipulation/Synthesis) ────────────────
        if deepfake_result:
            penalty = deepfake_result.confidence * 0.4
            final_score -= penalty
            component_scores["deepfake"] = round((1.0 - deepfake_result.confidence) * 100, 1)

        if voice_result:
            penalty = voice_result.anomaly_score * 0.3
            final_score -= penalty
            component_scores["voice"] = round((1.0 - voice_result.anomaly_score) * 100, 1)

        if ai_content_result:
            penalty = ai_content_result.ai_generated_probability * 0.3
            final_score -= penalty
            component_scores["ai_content"] = round((1.0 - ai_content_result.ai_generated_probability) * 100, 1)

        trust_score = int(round(final_score * 100))
        trust_score = max(0, min(100, trust_score))

        # Determine verdict
        verdict = self._determine_verdict(trust_score, text_result)

        logger.info(
            f"Credibility score: {trust_score}/100, verdict={verdict}, "
            f"components={component_scores}"
        )

        return CredibilityScore(
            trust_score=trust_score,
            verdict=verdict,
            component_scores=component_scores,
        )

    def _determine_verdict(
        self,
        trust_score: int,
        text_result: Optional[TextClassificationResult] = None,
    ) -> str:
        """Determine the overall verdict based on trust score."""
        if trust_score >= 75:
            return "LIKELY AUTHENTIC"
        elif trust_score >= 55:
            return "UNCERTAIN — VERIFY"
        elif trust_score >= 35:
            return "LIKELY MISLEADING"
        else:
            return "LIKELY FALSE"
