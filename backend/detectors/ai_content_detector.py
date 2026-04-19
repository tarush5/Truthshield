"""
TruthShield — AI Content Detector
Detect AI-generated text via linguistic heuristics, SynthID pre-filter + C2PA watermark check.
"""

import logging
import math
import re
from typing import Optional

from backend.models.schemas import AIContentResult

logger = logging.getLogger(__name__)


class AIContentDetector:
    """
    Detect AI-generated content using linguistic heuristic analysis,
    SynthID pre-filtering, and C2PA watermark checking.
    """

    def __init__(self):
        pass

    def check_c2pa_watermark(self, file_path: str) -> Optional[dict]:
        """
        Check for C2PA/Content Credentials watermark in media files.
        
        Returns:
            dict with watermark info if found, None otherwise
        """
        try:
            # C2PA checking requires the c2pa-python library
            # This is a simplified check for JPEG/PNG EXIF metadata
            from PIL import Image
            from PIL.ExifTags import TAGS

            img = Image.open(file_path)
            exif = img.getexif()

            c2pa_markers = {}
            for tag_id, value in exif.items():
                tag = TAGS.get(tag_id, tag_id)
                if "c2pa" in str(tag).lower() or "content" in str(tag).lower():
                    c2pa_markers[str(tag)] = str(value)

            if c2pa_markers:
                return {"has_watermark": True, "markers": c2pa_markers}
            return None

        except Exception as e:
            logger.debug(f"C2PA check skipped: {e}")
            return None

    def check_synthid_watermark(self, text: str, file_path: Optional[str] = None) -> Optional[dict]:
        """
        Pre-filter check for Google SynthID.
        """
        # Simulated SynthID check logic for text/image
        return None

    def analyze(
        self, text: str, file_path: Optional[str] = None
    ) -> AIContentResult:
        """
        Analyze content for AI-generation indicators.

        Args:
            text: Text content to analyze
            file_path: Optional path to media file for C2PA/SynthID check

        Returns:
            AIContentResult with AI-generation probability and XAI explanation.
        """
        if not text or len(text.strip()) < 20:
            return AIContentResult(
                ai_generated_probability=0.0,
                method="insufficient_text",
                explanation="Text is too short for reliable AI detection."
            )

        methods_used = []
        probabilities = []
        explanations = []

        # 1. SynthID Pre-filter
        synth_id_result = self.check_synthid_watermark(text, file_path)
        if synth_id_result and synth_id_result.get("has_watermark"):
            methods_used.append("synthid_watermark")
            probabilities.append(1.0)
            explanations.append("Positive SynthID watermark detected. Definitive AI generation.")

        # 2. C2PA watermark check
        if file_path:
            c2pa_result = self.check_c2pa_watermark(file_path)
            if c2pa_result:
                methods_used.append("c2pa_watermark")
                prob = 0.9 if c2pa_result["has_watermark"] else 0.0
                probabilities.append(prob)
                if prob > 0:
                    explanations.append("C2PA Content Credentials indicate AI generation or significant manipulation.")

        # 3. Content-aware heuristic analysis (deterministic, no model loading needed)
        if not probabilities:
            methods_used.append("linguistic_heuristic")
            prob, expl = self._comprehensive_heuristic(text)
            probabilities.append(prob)
            explanations.append(expl)

        # Aggregate
        avg_probability = sum(probabilities) / len(probabilities) if probabilities else 0.0
        final_explanation = " | ".join(explanations)

        logger.info(
            f"AI content detection: probability={avg_probability:.3f}, methods={methods_used}"
        )

        return AIContentResult(
            ai_generated_probability=round(avg_probability, 4),
            method="+".join(methods_used),
            explanation=final_explanation,
        )

    def _comprehensive_heuristic(self, text: str) -> tuple:
        """
        Comprehensive deterministic heuristic for AI content detection.
        Returns (probability, explanation_string).
        
        Analyzes:
        1. Sentence length uniformity (AI tends to produce uniform sentences)
        2. Vocabulary richness / type-token ratio
        3. AI-specific phrase patterns
        4. Transition word density (AI overuses transitions)
        5. Hedging language density
        6. Paragraph structure regularity
        7. Exclamation / question mark usage
        """
        score = 0.0
        signals = []
        text_lower = text.lower()
        words = text_lower.split()
        word_count = len(words)

        if word_count < 5:
            return 0.0, "Text too short for heuristic analysis."

        # ── 1. Sentence length uniformity ─────────────────────────
        sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip() and len(s.strip().split()) >= 3]
        if len(sentences) >= 3:
            sentence_lengths = [len(s.split()) for s in sentences]
            mean_len = sum(sentence_lengths) / len(sentence_lengths)
            if mean_len > 0:
                variance = sum((l - mean_len) ** 2 for l in sentence_lengths) / len(sentence_lengths)
                std_dev = math.sqrt(variance)
                cv = std_dev / mean_len  # Coefficient of variation
                if cv < 0.20:
                    score += 0.20
                    signals.append(f"Very uniform sentence lengths (CV={cv:.2f})")
                elif cv < 0.35:
                    score += 0.08
                    signals.append(f"Somewhat uniform sentence lengths (CV={cv:.2f})")

        # ── 2. Vocabulary richness (Type-Token Ratio) ─────────────
        if word_count >= 20:
            unique_words = set(words)
            ttr = len(unique_words) / word_count
            # AI text often has moderate TTR (0.4-0.6), human text varies more
            if ttr < 0.35:
                score += 0.05  # Very repetitive — could be either
            elif 0.45 <= ttr <= 0.60 and word_count > 50:
                score += 0.10
                signals.append(f"Vocabulary richness in typical AI range (TTR={ttr:.2f})")

        # ── 3. AI-specific phrase patterns ────────────────────────
        ai_phrases = [
            "as an ai", "i cannot", "it's important to note",
            "in conclusion", "it is worth noting", "however, it is",
            "delve into", "it's crucial", "comprehensive",
            "in today's world", "in this article", "let's explore",
            "it is essential", "firstly", "secondly", "thirdly",
            "in summary", "to summarize", "overall,",
            "plays a crucial role", "serves as a", "it should be noted",
            "multifaceted", "nuanced", "landscape", "leverage",
            "arguably", "undeniably", "interestingly",
        ]
        ai_phrase_count = sum(1 for phrase in ai_phrases if phrase in text_lower)
        if ai_phrase_count >= 4:
            score += 0.25
            signals.append(f"Multiple AI-typical phrases detected ({ai_phrase_count})")
        elif ai_phrase_count >= 2:
            score += 0.12
            signals.append(f"Some AI-typical phrases detected ({ai_phrase_count})")
        elif ai_phrase_count >= 1:
            score += 0.05

        # ── 4. Transition word density ────────────────────────────
        transition_words = [
            "however", "moreover", "furthermore", "additionally",
            "consequently", "therefore", "nevertheless", "nonetheless",
            "in addition", "on the other hand", "in contrast",
            "as a result", "for instance", "for example",
            "specifically", "particularly", "notably",
        ]
        transition_count = sum(1 for tw in transition_words if tw in text_lower)
        transition_density = transition_count / max(word_count / 100, 1)
        if transition_density > 3.0:
            score += 0.15
            signals.append(f"High transition word density ({transition_count} transitions)")
        elif transition_density > 1.5:
            score += 0.06

        # ── 5. Hedging language ───────────────────────────────────
        hedging_phrases = [
            "perhaps", "potentially", "arguably", "seemingly",
            "it appears", "it seems", "may be", "might be",
            "could be", "it is possible", "one could argue",
        ]
        hedge_count = sum(1 for h in hedging_phrases if h in text_lower)
        if hedge_count >= 4:
            score += 0.12
            signals.append(f"Excessive hedging language ({hedge_count} instances)")
        elif hedge_count >= 2:
            score += 0.05

        # ── 6. Emotional marker check (AI tends to lack them) ─────
        exclamation_count = text.count("!")
        question_count = text.count("?")
        allcaps_words = sum(1 for w in text.split() if w.isupper() and len(w) > 1)
        
        if word_count > 30 and exclamation_count == 0 and question_count == 0 and allcaps_words == 0:
            score += 0.05
            signals.append("No emotional markers (exclamations, questions, emphasis)")

        # ── 7. List / bullet point structure ──────────────────────
        list_markers = len(re.findall(r'^\s*[\-\*\d]+[\.\)]\s', text, re.MULTILINE))
        if list_markers >= 3 and word_count > 50:
            score += 0.08
            signals.append(f"Structured list format detected ({list_markers} items)")

        # ── Clamp final score ─────────────────────────────────────
        score = min(max(score, 0.0), 0.90)

        explanation = (
            f"Linguistic heuristic analysis: AI probability={score:.2f}. "
            + ("; ".join(signals) if signals else "No strong AI signals detected.")
        )

        return round(score, 4), explanation
