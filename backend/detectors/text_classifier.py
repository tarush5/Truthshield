"""
TruthShield — Text Classifier
Multilingual fake news detection using XLM-RoBERTa.
Supports English, Hindi, Tamil on LIAR-style labels.
"""

import logging
from typing import List, Optional

from backend.models.schemas import TextClassificationResult

logger = logging.getLogger(__name__)


class TextClassifier:
    """
    Fine-tuned XLM-RoBERTa classifier for misinformation detection.
    Labels: fake, real, misleading
    """

    LABELS = ["real", "misleading", "fake"]

    def __init__(self):
        self._model = None
        self._tokenizer = None
        self._pipeline = None

    def _load_model(self):
        """Lazy-load the classification pipeline."""
        if self._pipeline is not None:
            return
        try:
            from transformers import pipeline as hf_pipeline

            # Use a fast distilbert zero-shot classifier as fallback
            # In production, replace with fine-tuned XLM-RoBERTa checkpoint if high latency is acceptable
            self._pipeline = hf_pipeline(
                "zero-shot-classification",
                model="typeform/distilbert-base-uncased-mnli",
                device=-1,  # CPU
            )
            logger.info("DistilBERT text classifier loaded.")
        except Exception as e:
            logger.error(f"Failed to load text classifier: {e}")
            self._pipeline = None

    def classify(self, text: str, lang: str = "en") -> TextClassificationResult:
        """
        Classify text as fake, real, or misleading.

        Args:
            text: Input text to classify
            lang: Language code (en/hi/ta)

        Returns:
            TextClassificationResult with label, confidence, explanation tokens
        """
        if not text or len(text.strip()) < 10:
            return TextClassificationResult(
                label="unknown",
                confidence=0.0,
                explanation_tokens=["Text too short for classification"],
            )

        try:
            self._load_model()
            if self._pipeline is None:
                return self._fallback_classify(text)

            # Define candidate labels based on language
            if lang == "hi":
                candidate_labels = [
                    "सत्य समाचार",      # real news
                    "भ्रामक समाचार",     # misleading news
                    "झूठी खबर",          # fake news
                ]
            elif lang == "ta":
                candidate_labels = [
                    "உண்மையான செய்தி",   # real news
                    "தவறான செய்தி",      # misleading news
                    "போலி செய்தி",       # fake news
                ]
            else:
                candidate_labels = [
                    "verified factual news",
                    "misleading or biased news",
                    "fabricated fake news",
                ]

            result = self._pipeline(
                text[:512],  # Limit input length
                candidate_labels=candidate_labels,
                multi_label=False,
            )

            # result["labels"] is sorted by score descending — the top label won
            winning_candidate = result["labels"][0]
            top_score = result["scores"][0]

            # Build a reverse map: candidate label string → our internal label
            # candidate_labels order is always [real, misleading, fake]
            candidate_to_internal = {
                candidate_labels[0]: "real",
                candidate_labels[1]: "misleading",
                candidate_labels[2]: "fake",
            }
            label = candidate_to_internal.get(winning_candidate, "unknown")

            logger.info(
                f"Zero-shot classifier result: winning='{winning_candidate}' "
                f"→ label='{label}', confidence={top_score:.4f}"
            )

            # Extract key tokens (words that appear in high-attention positions)
            explanation_tokens = self._extract_key_tokens(text, label)

            return TextClassificationResult(
                label=label,
                confidence=round(top_score, 4),
                explanation_tokens=explanation_tokens,
            )

        except Exception as e:
            logger.error(f"Text classification failed: {e}")
            return self._fallback_classify(text)

    def _fallback_classify(self, text: str) -> TextClassificationResult:
        """Heuristic fallback when model is unavailable."""
        import re

        text_lower = text.lower()

        # ── Exact-match indicators ────────────────────────────────
        fake_indicators_exact = [
            "you won't believe", "they don't want you to know",
            "forwarded as received", "100% true",
            "जरूर शेयर करें", "वायरल", "सच्चाई",
        ]

        # ── Substring indicators (partial match inside text) ──────
        fake_indicators_partial = [
            "breaking", "shocking", "exposed", "secret",
            "share before", "share now", "must watch", "must share",
            "viral", "just in", "urgent",
            "before they delete", "before it's deleted", "before deleted",
            "they are hiding", "exposed", "conspiracy",
            "government doesn't want", "doctors don't want",
            "banned", "censored", "suppressed",
            "wake up", "open your eyes", "the truth about",
            "exposed", "bombshell", "unbelievable",
        ]

        credible_indicators = [
            "according to", "sources say", "reported by", "official statement",
            "press release", "data shows", "study finds", "research indicates",
            "peer-reviewed", "published in", "the study",
        ]

        # Factual / neutral statement patterns — simple declarative knowledge
        factual_patterns = [
            r"\b(has|have|is|are|was|were|contains?)\s+(\w+\s+){0,3}(\d+|many|several|multiple|few|various)",
            r"\b\d+\s*(colors?|sides?|legs?|types?|kinds?|parts?|elements?|planets?|continents?|oceans?|days?|months?|years?|seasons?)\b",
            r"\b(known as|called|defined as|refers to|consists of|composed of)\b",
            r"\b(science|mathematics|physics|chemistry|biology|geography|history)\b",
        ]

        fake_count = sum(1 for ind in fake_indicators_exact if ind in text_lower)
        fake_count += sum(1 for ind in fake_indicators_partial if ind in text_lower)
        credible_count = sum(1 for ind in credible_indicators if ind in text_lower)
        factual_count = sum(
            1 for pat in factual_patterns if re.search(pat, text_lower)
        )

        # Check for excessive punctuation/caps (common in fake news)
        words = text.split()
        allcaps_words = sum(1 for w in words if w.isupper() and len(w) > 1)
        caps_ratio = allcaps_words / max(len(words), 1)
        exclamation_count = text.count("!")

        # Start from a lower baseline so neutral/factual text defaults to "real"
        score = 0.30
        score += fake_count * 0.14
        score -= credible_count * 0.10
        score -= factual_count * 0.06  # Factual patterns reduce fake-score
        score += min(caps_ratio * 0.6, 0.25)
        score += min(exclamation_count * 0.06, 0.18)

        # If the text has NO misinformation signals AND is calm, treat as factual
        if fake_count == 0 and exclamation_count == 0 and caps_ratio < 0.15:
            score -= 0.05  # Extra nudge toward "real"

        score = max(0.0, min(1.0, score))

        if score > 0.55:
            label = "fake"
        elif score > 0.40:
            label = "misleading"
        else:
            label = "real"

        # Confidence is higher when score is further from the neutral zone
        if label == "fake":
            confidence = round(min((score - 0.55) * 3.0 + 0.5, 0.95), 4)
        elif label == "real":
            confidence = round(min((0.40 - score) * 3.0 + 0.5, 0.95), 4)
        else:
            confidence = round(abs(score - 0.475) * 2.0 + 0.3, 4)
        confidence = max(0.1, min(confidence, 0.95))

        return TextClassificationResult(
            label=label,
            confidence=confidence,
            explanation_tokens=[
                f"Heuristic analysis (model unavailable)",
                f"Fake indicators: {fake_count}",
                f"Credible indicators: {credible_count}",
                f"Factual patterns: {factual_count}",
                f"ALL-CAPS words: {allcaps_words}",
            ],
        )

    def _extract_key_tokens(self, text: str, label: str) -> List[str]:
        """Extract key tokens that may explain the classification."""
        import re
        words = re.findall(r"\b\w+\b", text.lower())
        # Return first few significant words
        stopwords = {"the", "a", "an", "is", "was", "are", "in", "on", "at", "to", "for", "of", "and", "or"}
        key_words = [w for w in words if w not in stopwords and len(w) > 3][:10]
        return key_words
