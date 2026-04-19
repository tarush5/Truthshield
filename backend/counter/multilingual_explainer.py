"""
TruthShield — Multilingual Explainer
Generate simple, jargon-free explanations in English, Hindi, and Tamil using Claude.
"""

import json
import logging
from typing import Optional

from backend.config import CLAUDE_MAX_TOKENS, CLAUDE_MODEL, get_settings
from backend.models.schemas import Explanation

logger = logging.getLogger(__name__)

EXPLAINER_SYSTEM_PROMPT = """You are a fact-checker. Explain why this content is {verdict} in simple language.
Respond in {lang}. Keep it under 100 words. Use no jargon.
Do not mention that you are an AI. Speak directly about the content.

Respond with ONLY the explanation text, no JSON, no formatting."""


class MultilingualExplainer:
    """Generate simple explanations in multiple languages via Claude."""

    LANG_NAMES = {"en": "English", "hi": "Hindi", "ta": "Tamil"}

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic

                settings = get_settings()
                self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            except Exception as e:
                logger.error(f"Failed to init Anthropic client: {e}")
        return self._client

    def explain(
        self, content_summary: str, verdict: str, evidence_summary: str = ""
    ) -> Explanation:
        """
        Generate explanations in all three supported languages.

        Args:
            content_summary: Brief description of the analyzed content
            verdict: The determined verdict (TRUE/FALSE/MISLEADING/UNVERIFIED)
            evidence_summary: Summary of key evidence

        Returns:
            Explanation with text in en, hi, ta
        """
        explanations = {}
        for lang_code, lang_name in self.LANG_NAMES.items():
            text = self._generate_explanation(
                content_summary, verdict, evidence_summary, lang_code, lang_name
            )
            explanations[lang_code] = text

        return Explanation(
            text_en=explanations.get("en", ""),
            text_hi=explanations.get("hi", ""),
            text_ta=explanations.get("ta", ""),
        )

    def _generate_explanation(
        self,
        content_summary: str,
        verdict: str,
        evidence_summary: str,
        lang_code: str,
        lang_name: str,
    ) -> str:
        """Generate a single language explanation."""
        client = self._get_client()

        if client is None:
            return self._fallback_explanation(verdict, lang_code)

        try:
            system = EXPLAINER_SYSTEM_PROMPT.format(
                verdict=verdict, lang=lang_name
            )

            user_message = f"""Content: {content_summary[:500]}

Verdict: {verdict}

Key Evidence: {evidence_summary[:300] if evidence_summary else 'No specific evidence available.'}

Provide a simple explanation in {lang_name}."""

            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=300,
                system=system,
                messages=[{"role": "user", "content": user_message}],
            )

            return response.content[0].text.strip()

        except Exception as e:
            logger.error(f"Explanation generation failed ({lang_code}): {e}")
            return self._fallback_explanation(verdict, lang_code)

    def _fallback_explanation(self, verdict: str, lang_code: str) -> str:
        """Provide basic fallback explanations."""
        fallbacks = {
            "en": {
                "TRUE": "This content appears to be accurate based on available evidence.",
                "FALSE": "This content contains false claims that contradict verified information.",
                "MISLEADING": "This content mixes facts with misleading information. Key details may be out of context.",
                "UNVERIFIED": "We could not verify this content. Please check official sources before sharing.",
            },
            "hi": {
                "TRUE": "उपलब्ध साक्ष्यों के आधार पर यह सामग्री सटीक प्रतीत होती है।",
                "FALSE": "इस सामग्री में झूठे दावे हैं जो सत्यापित जानकारी के विरुद्ध हैं।",
                "MISLEADING": "इस सामग्री में तथ्य और भ्रामक जानकारी मिली-जुली है।",
                "UNVERIFIED": "हम इस सामग्री की पुष्टि नहीं कर सके। कृपया साझा करने से पहले आधिकारिक स्रोत जांचें।",
            },
            "ta": {
                "TRUE": "கிடைக்கக்கூடிய ஆதாரங்களின் அடிப்படையில் இந்த உள்ளடக்கம் துல்லியமாகத் தெரிகிறது.",
                "FALSE": "இந்த உள்ளடக்கத்தில் சரிபார்க்கப்பட்ட தகவலுக்கு முரணான தவறான கூற்றுகள் உள்ளன.",
                "MISLEADING": "இந்த உள்ளடக்கம் உண்மைகளையும் தவறான தகவல்களையும் கலந்து காட்டுகிறது.",
                "UNVERIFIED": "இந்த உள்ளடக்கத்தை சரிபார்க்க முடியவில்லை. பகிர்வதற்கு முன் அதிகாரப்பூர்வ ஆதாரங்களை சரிபார்க்கவும்.",
            },
        }

        lang_fallbacks = fallbacks.get(lang_code, fallbacks["en"])
        return lang_fallbacks.get(verdict, lang_fallbacks.get("UNVERIFIED", ""))
