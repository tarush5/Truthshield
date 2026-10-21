"""
Image engine (Phase 2 scope: screenshots and photos of text).

    image → safe decode (pixel cap) → EXIF metadata → QR codes → OCR → text engine

QR codes are decoded (OpenCV, already a dependency) because "quishing" puts
the link where no text rule can see it. A decoded web address joins the
investigation's URLs and goes through the URL engine like any other link; a
UPI payment code is reported with what scanning it would pay, since the
common QR scam is "scan this to receive money" -- scanning a payment code
only ever sends money.

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
MAX_QR_CODES = 5
QR_SCAN_MAX_SIDE = 2000


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

        qr_block = self._qr_codes(image, result)
        for code in qr_block.get("codes", []):
            if code["kind"] == "url" and code["payload"] not in ctx.urls:
                ctx.urls.append(code["payload"])

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
        result.artifacts["image"] = {**info, "exif": exif, "ocr": ocr_block, "qr": qr_block}
        result.features.update({"width": info["width"], "height": info["height"]})

    def _qr_codes(self, image, result: EngineResult) -> dict:
        """Decode QR codes. Never raises: a failure is reported as not checked."""
        try:
            import cv2
            import numpy as np
        except ImportError:
            result.limitations.append("QR codes were not checked (OpenCV is not installed).")
            return {"status": "unavailable"}
        try:
            scan = image
            longest = max(scan.size)
            if longest > QR_SCAN_MAX_SIDE:
                ratio = QR_SCAN_MAX_SIDE / longest
                scan = scan.resize((int(scan.width * ratio), int(scan.height * ratio)))
            gray = cv2.cvtColor(np.asarray(scan), cv2.COLOR_RGB2GRAY)
            ok, payloads, _points, _ = cv2.QRCodeDetector().detectAndDecodeMulti(gray)
        except Exception as exc:  # malformed images must not fail the engine
            result.limitations.append(f"QR codes could not be checked ({type(exc).__name__}).")
            return {"status": "error"}

        codes = []
        for payload in (payloads if ok else [])[:MAX_QR_CODES]:
            if payload:
                codes.append(self._describe_qr(payload[:2000]))
        undecoded = sum(1 for p in (payloads if ok else []) if not p)
        if undecoded:
            result.limitations.append(f"{undecoded} QR code(s) were found but could not be decoded.")
        for code in codes:
            if code["kind"] == "upi_payment":
                upi = code["upi"]
                result.signals.append(Signal(
                    code="qr_upi_payment", title="QR code that sends a payment", severity=Severity.INFO,
                    family=Family.DOCUMENT_MEDIA, provenance=Provenance.HEURISTIC,
                    engine=self.name, engine_version=self.version,
                    explanation=(
                        f"Scanning this QR code pays {upi.get('payee') or 'the payee'}"
                        + (f" Rs {upi['amount']}" if upi.get("amount") else "")
                        + ". A QR code can only send money from the person who scans it, never receive it; "
                        "anyone saying 'scan to receive' is asking you to pay."
                    ),
                    evidence=code["payload"][:200], confidence=0.9,
                ))
        return {"status": "done", "count": len(codes), "codes": codes}

    @staticmethod
    def _describe_qr(payload: str) -> dict:
        from urllib.parse import parse_qs, urlparse

        lowered = payload.strip().lower()
        if lowered.startswith(("http://", "https://")):
            return {"kind": "url", "payload": payload.strip()}
        if lowered.startswith("upi://"):
            query = parse_qs(urlparse(payload.strip()).query)
            first = {k: v[0] for k, v in query.items() if v}
            return {"kind": "upi_payment", "payload": payload.strip(), "upi": {
                "payee": first.get("pa"), "name": first.get("pn"), "amount": first.get("am"),
                "note": first.get("tn"),
            }}
        return {"kind": "text", "payload": payload}

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
