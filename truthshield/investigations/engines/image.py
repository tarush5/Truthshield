"""
Image engine (Phase 2 scope: screenshots and photos of text).

    image → safe decode (pixel cap) → EXIF metadata → OCR → text engine

Screenshots of messages are among the most common things people want
checked, and their content is text: OCR turns them into input for the
same language, URL and evidence engines as a pasted message. Pixel-level
forensics (error-level analysis, copy-move, synthetic-image detection) are
Phase 3 and are listed as not performed.
"""

from __future__ import annotations

from typing import Optional

from truthshield.fraud.contract import Severity
from truthshield.investigations.engines.base import Engine
from truthshield.investigations.types import (
    EngineKind, EngineResult, EngineStatus, Family, InvestigationContext, InvestigationType,
    ModelPredictionRecord, Provenance, Signal,
)

EDITING_SOFTWARE = ("photoshop", "gimp", "snapseed", "picsart", "canva", "lightroom", "pixlr",
                    "affinity", "paint.net", "faceapp", "remini")
MAX_OCR_WORDS = 2000


class ImageEngine(Engine):
    name = "image"
    version = "1.0.0"
    kind = EngineKind.HEURISTIC
    describes = "Image metadata and OCR of screenshots (pixel forensics arrive in Phase 3)"

    def applies_to(self, ctx: InvestigationContext) -> bool:
        return ctx.type is InvestigationType.IMAGE and bool(ctx.file_path)

    def _run(self, ctx: InvestigationContext, result: EngineResult) -> None:
        from PIL import Image, UnidentifiedImageError

        from truthshield.providers import get_ocr_provider
        from truthshield.settings import get_settings

        Image.MAX_IMAGE_PIXELS = get_settings().MAX_IMAGE_PIXELS
        try:
            with Image.open(ctx.file_path) as img:
                img.load()
                image = img.convert("RGB")
                exif = self._exif(img)
                info = {"width": img.width, "height": img.height, "format": img.format, "mode": img.mode}
        except Image.DecompressionBombError:
            result.status = EngineStatus.ERROR
            result.detail = "Image exceeds the pixel limit."
            result.limitations.append("The image was not decoded: it exceeds the pixel limit (decompression-bomb guard).")
            return
        except (UnidentifiedImageError, OSError) as exc:
            result.status = EngineStatus.ERROR
            result.detail = "The image could not be decoded."
            result.limitations.append(f"The image could not be decoded ({type(exc).__name__}).")
            return

        software = (exif.get("Software") or "").lower()
        editor = next((e for e in EDITING_SOFTWARE if e in software), None)
        if editor:
            result.signals.append(Signal(
                code="image_editing_software", title="Edited with image software", severity=Severity.LOW,
                family=Family.DOCUMENT_MEDIA, provenance=Provenance.HEURISTIC,
                engine=self.name, engine_version=self.version,
                explanation="The image metadata names editing software. Most edits are innocent (cropping, "
                            "filters); for a screenshot offered as evidence it is worth asking for the original.",
                evidence=exif.get("Software"), confidence=0.4,
            ))

        provider = get_ocr_provider()
        ocr_block: dict
        if provider.available:
            ocr = provider.recognize(image)
            ctx.text = ocr.text
            ocr_block = {
                "status": "done", "engine": ocr.engine, "languages": ocr.languages,
                "mean_confidence": ocr.mean_confidence, "text": ocr.text[:20_000],
                "words": [{"text": w.text, "confidence": w.confidence, "bbox": w.bbox}
                          for w in ocr.words[:MAX_OCR_WORDS]],
            }
            if ocr.mean_confidence is not None and ocr.mean_confidence < 60:
                result.limitations.append(
                    f"OCR confidence is low ({ocr.mean_confidence:.0f}/100); text read from the image may contain errors."
                )
            result.predictions.append(ModelPredictionRecord(
                model_name=f"ocr.{ocr.engine}", model_version="1", model_kind=EngineKind.ML, task="ocr",
                input_sha256=ctx.input_sha256,
                prediction={"words": len(ocr.words), "chars": len(ocr.text)},
                confidence=round(ocr.mean_confidence / 100, 3) if ocr.mean_confidence is not None else None,
            ))
        else:
            ocr_block = {"status": "unavailable", "detail": provider.unavailable_reason}
            result.limitations.append(
                f"Text in the image was not read: OCR is unavailable ({provider.unavailable_reason}). "
                "Only the image metadata was examined."
            )

        result.limitations.append(
            "Pixel-level forensics (error-level analysis, copy-move detection, synthetic-image detection) "
            "were not performed; they arrive in Phase 3."
        )
        result.artifacts["image"] = {**info, "exif": exif, "ocr": ocr_block}
        result.features.update({"width": info["width"], "height": info["height"]})

    @staticmethod
    def _exif(img) -> dict:
        from PIL import ExifTags

        out = {}
        try:
            raw = img.getexif()
        except Exception:
            return out
        wanted = {"Software", "DateTime", "Make", "Model", "Artist", "ImageDescription"}
        for tag, value in raw.items():
            name: Optional[str] = ExifTags.TAGS.get(tag)
            if name in wanted and value:
                out[name] = str(value)[:200]
        return out
