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
        self._gemini_client = None
        self._claude_client = None
        self._gemini_checked = False
        self._claude_checked = False

    def _get_gemini_client(self):
        if not self._gemini_checked:
            self._gemini_checked = True
            try:
                from google import genai
                settings = get_settings()
                key = settings.GEMINI_API_KEY
                if key and key != "your_gemini_api_key" and len(key) > 10:
                    self._gemini_client = genai.Client(api_key=key)
            except Exception as e:
                logger.warning(f"Gemini init failed: {e}")
        return self._gemini_client

    def _get_claude_client(self):
        if not self._claude_checked:
            self._claude_checked = True
            try:
                import anthropic
                settings = get_settings()
                key = settings.ANTHROPIC_API_KEY
                if key and key != "your_anthropic_api_key" and len(key) > 10:
                    self._claude_client = anthropic.Anthropic(api_key=key)
            except Exception as e:
                logger.warning(f"Claude init failed: {e}")
        return self._claude_client

    def explain(
        self, content_summary: str, verdict: str, evidence_summary: str = ""
    ) -> Explanation:
        """
        Generate explanations in all three supported languages in a single LLM call.

        Args:
            content_summary: Brief description of the analyzed content
            verdict: The determined verdict (TRUE/FALSE/MISLEADING/UNVERIFIED)
            evidence_summary: Summary of key evidence

        Returns:
            Explanation with text in en, hi, ta
        """
        # Try single-query multilingual generation (3x faster than sequential)
        result = self._generate_all_languages(content_summary, verdict, evidence_summary)
        if result:
            return result

        # Fallback to sequential generation if single-query fails
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

    def _generate_all_languages(
        self, content_summary: str, verdict: str, evidence_summary: str
    ) -> Optional[Explanation]:
        """Generate explanations in all 3 languages in a single LLM call."""
        system_prompt = """You are a fact-checker. Explain why content is flagged in simple language.
Keep each explanation under 100 words. Use no jargon. Do not mention that you are an AI.

Respond with ONLY a JSON object (no markdown, no code fences):
{
    "en": "English explanation",
    "hi": "Hindi explanation",
    "ta": "Tamil explanation"
}"""
        user_message = f"""Content: {content_summary[:500]}
Verdict: {verdict}
Key Evidence: {evidence_summary[:300] if evidence_summary else 'No specific evidence available.'}

Generate simple explanations in English, Hindi, and Tamil."""

        # Try Gemini first
        gemini = self._get_gemini_client()
        if gemini:
            try:
                from backend.config import GEMINI_MODEL
                from google.genai import types
                response = gemini.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=user_message,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.2,
                    )
                )
                return self._parse_multilingual_response(response.text.strip(), verdict)
            except Exception as e:
                logger.warning(f"Gemini multilingual generation failed: {e}")

        # Try Claude
        claude = self._get_claude_client()
        if claude:
            try:
                response = claude.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=600,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                )
                return self._parse_multilingual_response(response.content[0].text.strip(), verdict)
            except Exception as e:
                logger.warning(f"Claude multilingual generation failed: {e}")

        return None

    def _parse_multilingual_response(self, response_text: str, verdict: str) -> Optional[Explanation]:
        """Parse a multilingual JSON response into an Explanation."""
        try:
            # Strip markdown code fences if present
            text = response_text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            
            result = json.loads(text)
            en = result.get("en", "")
            hi = result.get("hi", "")
            ta = result.get("ta", "")
            
            if en:  # At minimum we need English
                return Explanation(
                    text_en=en,
                    text_hi=hi or self._fallback_explanation(verdict, "hi"),
                    text_ta=ta or self._fallback_explanation(verdict, "ta"),
                )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse multilingual response: {e}")
        return None

    def _generate_explanation(
        self,
        content_summary: str,
        verdict: str,
        evidence_summary: str,
        lang_code: str,
        lang_name: str,
    ) -> str:
        """Generate a single language explanation."""
        # 1. Try Gemini
        gemini = self._get_gemini_client()
        if gemini:
            try:
                from backend.config import GEMINI_MODEL
                system = EXPLAINER_SYSTEM_PROMPT.format(
                    verdict=verdict, lang=lang_name
                )
                user_message = f"""Content: {content_summary[:500]}

Verdict: {verdict}

Key Evidence: {evidence_summary[:300] if evidence_summary else 'No specific evidence available.'}

Provide a simple explanation in {lang_name}."""

                from google.genai import types
                response = gemini.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=user_message,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        temperature=0.2,
                    )
                )
                return response.text.strip()
            except Exception as e:
                logger.warning(f"Gemini explanation generation failed ({lang_code}): {e}")

        # 2. Try Claude
        claude = self._get_claude_client()
        if claude:
            try:
                system = EXPLAINER_SYSTEM_PROMPT.format(
                    verdict=verdict, lang=lang_name
                )
                user_message = f"""Content: {content_summary[:500]}

Verdict: {verdict}

Key Evidence: {evidence_summary[:300] if evidence_summary else 'No specific evidence available.'}

Provide a simple explanation in {lang_name}."""

                response = claude.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=300,
                    system=system,
                    messages=[{"role": "user", "content": user_message}],
                )
                return response.content[0].text.strip()
            except Exception as e:
                logger.warning(f"Claude explanation generation failed ({lang_code}): {e}")

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
