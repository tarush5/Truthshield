"""
OCR providers.

`TesseractOCR` needs the Tesseract **binary** (the `pytesseract` package alone
imports fine on a machine with no OCR at all -- 1.x learned this the hard
way). Languages are intersected with the installed traineddata, so asking for
Tamil on a server without `tam.traineddata` is reported rather than failing.
"""

from __future__ import annotations

import shutil
from functools import lru_cache
from typing import Optional

from truthshield.providers.base import BaseOCRProvider, OCRResult, OCRWord


class UnavailableOCR(BaseOCRProvider):
    name = "none"

    def __init__(self, reason: str):
        self._reason = reason

    @property
    def available(self) -> bool:
        return False

    @property
    def unavailable_reason(self) -> Optional[str]:
        return self._reason

    def recognize(self, image, *, languages: Optional[str] = None) -> OCRResult:
        raise RuntimeError(self._reason)


class TesseractOCR(BaseOCRProvider):
    name = "tesseract"

    def __init__(self, languages: str = "eng"):
        self._requested = languages
        self._installed: Optional[set] = None

    @property
    def available(self) -> bool:
        if not shutil.which("tesseract"):
            return False
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    @property
    def unavailable_reason(self) -> Optional[str]:
        return None if self.available else "The Tesseract OCR binary is not installed."

    def languages(self, requested: Optional[str] = None) -> str:
        import pytesseract

        if self._installed is None:
            try:
                self._installed = set(pytesseract.get_languages(config=""))
            except Exception:
                self._installed = {"eng"}
        wanted = [code for code in (requested or self._requested).split("+") if code]
        usable = [code for code in wanted if code in self._installed]
        return "+".join(usable) or "eng"

    def recognize(self, image, *, languages: Optional[str] = None) -> OCRResult:
        import pytesseract

        langs = self.languages(languages)
        data = pytesseract.image_to_data(image, lang=langs, output_type=pytesseract.Output.DICT, timeout=60)
        words, lines, current = [], [], []
        last_line = None
        for i, text in enumerate(data["text"]):
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            if last_line is not None and key != last_line and current:
                lines.append(" ".join(current))
                current = []
            last_line = key
            if not text or not text.strip():
                continue
            conf = float(data["conf"][i])
            words.append(OCRWord(
                text=text,
                confidence=conf,
                bbox=[int(data["left"][i]), int(data["top"][i]), int(data["width"][i]), int(data["height"][i])],
            ))
            current.append(text)
        if current:
            lines.append(" ".join(current))
        return OCRResult(text="\n".join(lines), words=words, languages=langs, engine=self.name)


@lru_cache
def get_ocr_provider() -> BaseOCRProvider:
    from truthshield.settings import get_settings

    s = get_settings()
    choice = s.OCR_PROVIDER.strip().lower()
    if choice == "none":
        return UnavailableOCR("OCR_PROVIDER is set to none.")
    tesseract = TesseractOCR(s.OCR_LANGUAGES)
    if tesseract.available:
        return tesseract
    return UnavailableOCR("The Tesseract OCR binary is not installed on this server.")


def reset_ocr_provider() -> None:
    get_ocr_provider.cache_clear()
