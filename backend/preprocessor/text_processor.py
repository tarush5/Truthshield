"""
TruthShield — Text Processor
Detects language and prepares text content for analysis.
"""

import logging
from typing import Optional

from langdetect import detect, DetectorFactory

from backend.models.schemas import ContentPacket, ContentType, Language

# Ensure deterministic language detection
DetectorFactory.seed = 0

logger = logging.getLogger(__name__)

# Map langdetect codes to our Language enum
LANG_MAP = {
    "en": Language.EN,
    "hi": Language.HI,
    "ta": Language.TA,
}


class TextProcessor:
    """Process raw text input into a standardized ContentPacket."""

    @staticmethod
    def detect_language(text: str) -> Language:
        """Detect the language of input text."""
        try:
            detected = detect(text)
            return LANG_MAP.get(detected, Language.EN)
        except Exception as e:
            logger.warning(f"Language detection failed: {e}. Defaulting to English.")
            return Language.EN

    @staticmethod
    def clean_text(text: str) -> str:
        """Basic text cleaning — normalize whitespace, strip control chars."""
        import re
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
        return text

    def process(self, text: str, lang_hint: Optional[str] = None) -> ContentPacket:
        """
        Process raw text into a ContentPacket.
        
        Args:
            text: Raw input text
            lang_hint: Optional language hint (en/hi/ta)
        
        Returns:
            ContentPacket with cleaned text and detected language
        """
        cleaned = self.clean_text(text)

        if lang_hint and lang_hint in [l.value for l in Language]:
            lang = Language(lang_hint)
        else:
            lang = self.detect_language(cleaned)

        logger.info(f"Text processed: {len(cleaned)} chars, language={lang.value}")

        return ContentPacket(
            content_type=ContentType.TEXT,
            text=cleaned,
            lang=lang,
            metadata={
                "original_length": len(text),
                "cleaned_length": len(cleaned),
                "detected_language": lang.value,
            },
        )
