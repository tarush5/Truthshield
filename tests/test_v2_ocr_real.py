"""
Real OCR through the Tesseract provider. Skipped where the binary is absent;
CI installs `tesseract-ocr` so this runs on every push.
"""

import shutil

import pytest

pytestmark = pytest.mark.skipif(not shutil.which("tesseract"), reason="Tesseract binary not installed")


def test_tesseract_reads_rendered_text_with_boxes_and_confidence():
    from PIL import Image, ImageDraw, ImageFont

    from truthshield.providers.ocr import TesseractOCR

    image = Image.new("RGB", (900, 200), "white")
    draw = ImageDraw.Draw(image)
    draw.text((30, 60), "INVOICE 48213 TOTAL 9500", fill="black", font=ImageFont.load_default(size=56))

    provider = TesseractOCR("eng")
    assert provider.available
    result = provider.recognize(image)
    assert "48213" in result.text and "INVOICE" in result.text.upper()
    assert result.words and all(len(w.bbox) == 4 for w in result.words)
    assert result.mean_confidence and result.mean_confidence > 50
