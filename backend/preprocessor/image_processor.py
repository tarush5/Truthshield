"""
TruthShield — Image Processor
OCR extraction via Tesseract + image captioning preparation.
"""

import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from backend.models.schemas import ContentPacket, ContentType, Language

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Process image files — extract OCR text and generate captions."""

    def __init__(self):
        self._ocr_available = False
        try:
            import pytesseract
            self._pytesseract = pytesseract
            self._ocr_available = True
        except ImportError:
            logger.warning("pytesseract not available. OCR disabled.")

    def extract_ocr_text(self, image_path: str, lang: str = "eng") -> str:
        """Extract text from image using Tesseract OCR."""
        if not self._ocr_available:
            return ""
        try:
            from PIL import Image
            img = Image.open(image_path)
            # Map our lang codes to Tesseract codes
            tess_lang_map = {"en": "eng", "hi": "hin", "ta": "tam"}
            tess_lang = tess_lang_map.get(lang, "eng")
            text = self._pytesseract.image_to_string(img, lang=tess_lang)
            return text.strip()
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return ""

    def generate_caption(self, image_path: str) -> str:
        """
        Generate image caption using BLIP-2.
        Falls back to a placeholder if model not available.
        """
        try:
            from transformers import BlipProcessor, BlipForConditionalGeneration
            from PIL import Image

            processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
            model = BlipForConditionalGeneration.from_pretrained(
                "Salesforce/blip-image-captioning-base"
            )
            img = Image.open(image_path).convert("RGB")
            inputs = processor(img, return_tensors="pt")
            out = model.generate(**inputs, max_new_tokens=50)
            caption = processor.decode(out[0], skip_special_tokens=True)
            return caption
        except Exception as e:
            logger.warning(f"Caption generation failed: {e}. Using fallback.")
            return ""

    def process(
        self, image_path: str, lang_hint: Optional[str] = None
    ) -> ContentPacket:
        """
        Process an image into a ContentPacket.

        Args:
            image_path: Path to the image file
            lang_hint: Optional language hint for OCR

        Returns:
            ContentPacket with OCR text and caption metadata
        """
        lang = lang_hint or "en"
        ocr_text = self.extract_ocr_text(image_path, lang)
        caption = self.generate_caption(image_path)

        combined_text = ""
        if ocr_text:
            combined_text = f"[OCR] {ocr_text}"
        if caption:
            combined_text += f"\n[Caption] {caption}" if combined_text else f"[Caption] {caption}"

        from backend.preprocessor.text_processor import TextProcessor
        detected_lang = TextProcessor.detect_language(ocr_text) if ocr_text else Language.EN

        logger.info(f"Image processed: OCR={len(ocr_text)} chars, caption generated")

        return ContentPacket(
            content_type=ContentType.IMAGE,
            text=combined_text or None,
            lang=detected_lang,
            image_paths=[image_path],
            metadata={
                "ocr_text": ocr_text,
                "caption": caption,
                "has_text": bool(ocr_text),
            },
        )
