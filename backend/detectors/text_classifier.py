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

    # ── Class-level model cache (singleton per process) ──────
    _shared_pipeline = None
    _shared_pipeline_loaded = False

    def __init__(self):
        self._model = None
        self._tokenizer = None
        self._pipeline = None

    def _get_gemini_client(self):
        """Lazy-initialize Google Gemini client."""
        try:
            from backend.config import get_settings
            settings = get_settings()
            key = settings.GEMINI_API_KEY
            if key and key != "your_gemini_api_key" and len(key) > 10:
                from google import genai
                return genai.Client(api_key=key)
        except Exception as e:
            logger.warning(f"Failed to initialize Gemini client in TextClassifier: {e}")
        return None

    def _load_model(self):
        """Lazy-load the classification pipeline (cached at class level)."""
        # Use class-level cache so model loads once per process
        if TextClassifier._shared_pipeline_loaded:
            self._pipeline = TextClassifier._shared_pipeline
            return

        import os
        # If running on Render or low-memory environment, do not load Hugging Face models (prevents OOM crashes)
        if os.getenv("LOW_MEMORY") == "true" or os.getenv("RENDER") == "true":
            logger.info("Low memory or Render environment detected. Skipping Hugging Face model loading for TextClassifier.")
            TextClassifier._shared_pipeline_loaded = True
            self._pipeline = None
            return

        try:
            from transformers import pipeline as hf_pipeline

            # Use a fast distilbert zero-shot classifier as fallback
            # In production, replace with fine-tuned XLM-RoBERTa checkpoint if high latency is acceptable
            TextClassifier._shared_pipeline = hf_pipeline(
                "zero-shot-classification",
                model="typeform/distilbert-base-uncased-mnli",
                device=-1,  # CPU
            )
            TextClassifier._shared_pipeline_loaded = True
            self._pipeline = TextClassifier._shared_pipeline
            logger.info("DistilBERT text classifier loaded (cached at class level).")
        except Exception as e:
            logger.error(f"Failed to load text classifier: {e}")
            TextClassifier._shared_pipeline_loaded = True  # Don't retry on failure
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
            # Try Gemini API zero-shot classification first if key is available (almost zero memory, very accurate)
            gemini_client = self._get_gemini_client()
            if gemini_client:
                try:
                    import json
                    import re
                    from backend.config import GEMINI_MODEL
                    from google.genai import types

                    # Define candidate labels in English to be parsed deterministically
                    prompt = f"""You are an AI misinformation classifier. Classify the following text into one of these categories:
- real: Verified factual news or content
- misleading: Contains some truth but is out of context, exaggerated, or biased
- fake: Fabricated, demonstrably false, or completely untrue content

TEXT: {text[:800]}
LANGUAGE: {lang}

Respond with ONLY valid JSON:
{{"label": "real"|"misleading"|"fake", "confidence": 0.0-1.0}}"""

                    response = gemini_client.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            max_output_tokens=100,
                            temperature=0.1,
                        ),
                    )
                    res_text = response.text.strip()
                    if "```json" in res_text:
                        res_text = res_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in res_text:
                        res_text = res_text.split("```")[1].split("```")[0].strip()

                    json_match = re.search(r'\{[^{}]*"label"[^{}]*\}', res_text, re.DOTALL)
                    if json_match:
                        res_text = json_match.group(0)

                    res = json.loads(res_text)
                    label = res.get("label", "real").lower()
                    if label not in ("real", "misleading", "fake"):
                        label = "real"
                    confidence = float(res.get("confidence", 0.8))

                    # Combine with heuristic score as secondary signal
                    h_score = self._calculate_heuristic_score(text)
                    
                    # Nudge confidence based on heuristic alignment
                    if label == "fake" and h_score > 0.5:
                        confidence = min(0.98, confidence + 0.05)
                    elif label == "real" and h_score < 0.4:
                        confidence = min(0.98, confidence + 0.05)

                    explanation_tokens = self._extract_key_tokens(text, label)
                    explanation_tokens.append("API-based classification (Gemini)")

                    logger.info(f"Gemini text classifier result: label='{label}', confidence={confidence:.4f}")
                    return TextClassificationResult(
                        label=label,
                        confidence=round(confidence, 4),
                        explanation_tokens=explanation_tokens,
                    )
                except Exception as e:
                    logger.warning(f"Gemini text classification failed, falling back to local/heuristic: {e}")

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

            # Build a reverse map: candidate label string → our internal label
            # candidate_labels order is always [real, misleading, fake]
            candidate_to_internal = {
                candidate_labels[0]: "real",
                candidate_labels[1]: "misleading",
                candidate_labels[2]: "fake",
            }

            # Get zero-shot model probabilities
            model_probs = {}
            for label_str, score_val in zip(result["labels"], result["scores"]):
                internal_label = candidate_to_internal.get(label_str, "unknown")
                if internal_label != "unknown":
                    model_probs[internal_label] = score_val

            # Get heuristic score and probabilities
            h_score = self._calculate_heuristic_score(text)
            
            import math
            d_real = abs(h_score - 0.2)
            d_misleading = abs(h_score - 0.475)
            d_fake = abs(h_score - 0.75)
            
            w_real = math.exp(-d_real * 5)
            w_misleading = math.exp(-d_misleading * 5)
            w_fake = math.exp(-d_fake * 5)
            
            total = w_real + w_misleading + w_fake
            h_probs = {
                "real": w_real / total,
                "misleading": w_misleading / total,
                "fake": w_fake / total,
            }

            # Combine model and heuristic probabilities
            # Model has 40% weight, heuristics have 60% weight
            combined_probs = {}
            for lbl in ["real", "misleading", "fake"]:
                combined_probs[lbl] = 0.4 * model_probs.get(lbl, 0.33) + 0.6 * h_probs[lbl]

            # Find the winning label
            label = max(combined_probs, key=combined_probs.get)
            confidence = round(combined_probs[label], 4)

            logger.info(
                f"Combined classifier result: model_probs={model_probs} "
                f"h_score={h_score:.2f} h_probs={h_probs} "
                f"→ label='{label}', confidence={confidence:.4f}"
            )

            # Extract key tokens (words that appear in high-attention positions)
            explanation_tokens = self._extract_key_tokens(text, label)
            explanation_tokens.append("Combined analysis (Model + Heuristics)")

            return TextClassificationResult(
                label=label,
                confidence=confidence,
                explanation_tokens=explanation_tokens,
            )

        except Exception as e:
            logger.error(f"Text classification failed: {e}")
            return self._fallback_classify(text)

    def _calculate_heuristic_score(self, text: str) -> float:
        """Calculate a heuristic score from 0.0 (definitely real) to 1.0 (definitely fake)."""
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
        return score

    def _fallback_classify(self, text: str) -> TextClassificationResult:
        """Heuristic fallback when model is unavailable."""
        score = self._calculate_heuristic_score(text)

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
                f"Heuristic score: {score:.2f}",
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
