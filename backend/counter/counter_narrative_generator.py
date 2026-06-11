"""
TruthShield — Counter-Narrative Generator
Generate fact-grounded counter-narratives in multiple languages via Claude.
"""

import json
import logging
from typing import List, Optional

from backend.config import CLAUDE_MAX_TOKENS, CLAUDE_MODEL, get_settings
from backend.models.schemas import ClaimVerdict, CounterNarrative

logger = logging.getLogger(__name__)

COUNTER_NARRATIVE_SYSTEM_PROMPT = """Generate a concise, factual counter-narrative grounded only in the verified evidence provided. Do not add unsupported claims. Cite sources inline using [Source N] markers.

Language: {lang}

Respond with ONLY a JSON object:
{{
    "summary": "The counter-narrative text with inline [Source N] citations",
    "sources_cited": ["url1", "url2"]
}}"""


class CounterNarrativeGenerator:
    """Generate factual counter-narratives in English, Hindi, Tamil."""

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

    def generate(
        self, original_text: str, claim_verdicts: List[ClaimVerdict]
    ) -> CounterNarrative:
        """
        Generate counter-narrative in all three languages in a single LLM call.

        Args:
            original_text: The original content text
            claim_verdicts: List of evaluated claim verdicts with evidence

        Returns:
            CounterNarrative with summaries in en, hi, ta and sources cited
        """
        # Collect all evidence sources
        all_sources = []
        evidence_text = ""
        for i, cv in enumerate(claim_verdicts):
            evidence_text += f"\nClaim {i+1}: {cv.claim.text}\n"
            evidence_text += f"Verdict: {cv.verdict.value}\n"
            evidence_text += f"Reasoning: {cv.reasoning}\n"
            for j, ev in enumerate(cv.evidence):
                evidence_text += f"  [Source {len(all_sources)+1}] {ev.title} ({ev.url}): {ev.snippet[:150]}\n"
                all_sources.append(ev.url)

        # Try single-query multilingual generation (3x faster)
        result = self._generate_all_languages(original_text, evidence_text)
        if result:
            return CounterNarrative(
                summary_en=result.get("en", ""),
                summary_hi=result.get("hi", ""),
                summary_ta=result.get("ta", ""),
                sources_cited=list(set(all_sources)),
            )

        # Fallback to sequential generation
        summaries = {}
        for lang_code, lang_name in self.LANG_NAMES.items():
            summary, sources = self._generate_single(
                original_text, evidence_text, lang_code, lang_name
            )
            summaries[lang_code] = summary

        return CounterNarrative(
            summary_en=summaries.get("en", ""),
            summary_hi=summaries.get("hi", ""),
            summary_ta=summaries.get("ta", ""),
            sources_cited=list(set(all_sources)),
        )

    def _generate_all_languages(self, original_text: str, evidence_text: str) -> Optional[dict]:
        """Generate counter-narratives in all 3 languages in a single LLM call."""
        system_prompt = """Generate concise, factual counter-narratives grounded only in verified evidence.
Do not add unsupported claims. Cite sources inline using [Source N] markers.

Respond with ONLY a JSON object (no markdown, no code fences):
{
    "en": "English counter-narrative with [Source N] citations",
    "hi": "Hindi counter-narrative with [Source N] citations",
    "ta": "Tamil counter-narrative with [Source N] citations"
}"""
        user_message = f"""ORIGINAL CONTENT:
{original_text[:1000]}

VERIFIED EVIDENCE AND VERDICTS:
{evidence_text[:2000]}

Generate factual counter-narratives in English, Hindi, and Tamil."""

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
                return self._parse_multilingual_cn_response(response.text.strip())
            except Exception as e:
                logger.warning(f"Gemini multilingual CN generation failed: {e}")

        # Try Claude
        claude = self._get_claude_client()
        if claude:
            try:
                response = claude.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=CLAUDE_MAX_TOKENS,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                )
                return self._parse_multilingual_cn_response(response.content[0].text.strip())
            except Exception as e:
                logger.warning(f"Claude multilingual CN generation failed: {e}")

        return None

    def _parse_multilingual_cn_response(self, response_text: str) -> Optional[dict]:
        """Parse a multilingual JSON response into a dict with en/hi/ta keys."""
        try:
            text = response_text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            result = json.loads(text)
            if "en" in result:
                return result
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse multilingual CN response: {e}")
        return None

    def _generate_single(
        self,
        original_text: str,
        evidence_text: str,
        lang_code: str,
        lang_name: str,
    ) -> tuple:
        """Generate counter-narrative in a single language."""
        # 1. Try Gemini
        gemini = self._get_gemini_client()
        if gemini:
            try:
                from backend.config import GEMINI_MODEL
                system = COUNTER_NARRATIVE_SYSTEM_PROMPT.format(lang=lang_name)
                user_message = f"""ORIGINAL CONTENT:
{original_text[:1000]}

VERIFIED EVIDENCE AND VERDICTS:
{evidence_text[:2000]}

Generate a factual counter-narrative in {lang_name}."""

                from google.genai import types
                response = gemini.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=user_message,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        temperature=0.2,
                    )
                )
                response_text = response.text.strip()
                return self._parse_counter_narrative_response(response_text)
            except Exception as e:
                logger.warning(f"Gemini counter-narrative generation failed ({lang_code}): {e}")

        # 2. Try Claude
        claude = self._get_claude_client()
        if claude:
            try:
                system = COUNTER_NARRATIVE_SYSTEM_PROMPT.format(lang=lang_name)
                user_message = f"""ORIGINAL CONTENT:
{original_text[:1000]}

VERIFIED EVIDENCE AND VERDICTS:
{evidence_text[:2000]}

Generate a factual counter-narrative in {lang_name}."""

                response = claude.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=CLAUDE_MAX_TOKENS,
                    system=system,
                    messages=[{"role": "user", "content": user_message}],
                )
                response_text = response.content[0].text.strip()
                return self._parse_counter_narrative_response(response_text)
            except Exception as e:
                logger.warning(f"Claude counter-narrative generation failed ({lang_code}): {e}")

        return self._fallback_narrative(lang_code), []

    def _parse_counter_narrative_response(self, response_text: str) -> tuple:
        try:
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            result = json.loads(response_text)
            return (
                result.get("summary", response_text),
                result.get("sources_cited", []),
            )
        except json.JSONDecodeError:
            return response_text, []

    def _fallback_narrative(self, lang_code: str) -> str:
        """Provide fallback counter-narratives."""
        fallbacks = {
            "en": (
                "Based on available evidence, the claims in this content could not be fully verified. "
                "We recommend checking official sources and established fact-checking organizations "
                "before sharing this information further."
            ),
            "hi": (
                "उपलब्ध साक्ष्यों के आधार पर, इस सामग्री के दावों की पूरी तरह पुष्टि नहीं हो सकी। "
                "इस जानकारी को आगे साझा करने से पहले आधिकारिक स्रोतों और स्थापित "
                "तथ्य-जांच संगठनों की जांच करने की सिफारिश की जाती है।"
            ),
            "ta": (
                "கிடைக்கக்கூடிய ஆதாரங்களின் அடிப்படையில், இந்த உள்ளடக்கத்தின் கூற்றுகளை "
                "முழுமையாக சரிபார்க்க முடியவில்லை. இந்த தகவலை மேலும் பகிர்வதற்கு முன், "
                "அதிகாரப்பூர்வ ஆதாரங்கள் மற்றும் நிறுவப்பட்ட உண்மை சரிபார்ப்பு "
                "அமைப்புகளை சரிபார்க்க பரிந்துரைக்கிறோம்."
            ),
        }
        return fallbacks.get(lang_code, fallbacks["en"])
