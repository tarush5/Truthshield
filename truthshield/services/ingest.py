"""
Ingestion — turn any submission into a ContentPacket.

Every path that reaches out to the network or the filesystem is guarded, and
every extraction failure is recorded in the packet's metadata rather than
silently producing empty text. An empty `text` field with no explanation is
what let an unreadable image be scored as though it had been read.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Optional

from truthshield.domain.types import ContentPacket, ContentType, Language
from truthshield.security import BlockedURLError, safe_get

logger = logging.getLogger(__name__)

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}
AUDIO_EXT = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"}
VIDEO_EXT = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
DOC_EXT = {".pdf", ".txt", ".md", ".doc", ".docx"}


def classify_extension(filename: str) -> ContentType:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext in IMAGE_EXT:
        return ContentType.IMAGE
    if ext in AUDIO_EXT:
        return ContentType.AUDIO
    if ext in VIDEO_EXT:
        return ContentType.VIDEO
    if ext in DOC_EXT:
        return ContentType.DOCUMENT
    return ContentType.DOCUMENT


def build_packet(
    text: Optional[str],
    url: Optional[str],
    file_path: Optional[str],
    content_type: ContentType,
    language: Language,
) -> ContentPacket:
    packet = ContentPacket(
        content_type=content_type,
        language=language,
        text=(text or "").strip() or None,
        source_url=url,
        file_path=file_path,
    )

    if url and content_type is ContentType.URL:
        _from_url(packet, url)
    elif file_path:
        _from_file(packet, file_path, content_type)

    if packet.has_text:
        packet.text = _clean(packet.text)
        packet.language = _detect_language(packet.text, language)

    return packet


def _clean(text: str) -> str:
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _detect_language(text: str, fallback: Language) -> Language:
    try:
        from langdetect import detect, DetectorFactory
        DetectorFactory.seed = 0          # langdetect is nondeterministic otherwise
        code = detect(text)
        return Language(code) if code in {l.value for l in Language} else fallback
    except Exception:
        return fallback


def _from_url(packet: ContentPacket, url: str) -> None:
    """
    Fetch and extract an article.

    Goes through `safe_get`, which validates the scheme, every resolved
    address and every redirect hop. The fetched body is returned to the caller
    in the report, so an unguarded fetch here is a full-read SSRF.
    """
    try:
        response = safe_get(url)
        response.raise_for_status()
    except BlockedURLError as exc:
        packet.metadata["fetch_error"] = str(exc)
        return
    except Exception as exc:
        packet.metadata["fetch_error"] = f"Could not fetch the page: {exc}"
        return

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup.find_all(["script", "style", "nav", "footer", "header",
                                 "aside", "form", "noscript", "iframe"]):
            tag.decompose()

        title = (soup.title.string or "").strip() if soup.title else ""
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            title = og["content"].strip()

        body = ""
        for selector in ("article", "main", '[role="main"]', ".article-content", ".post-content"):
            container = soup.select_one(selector)
            if container:
                parts = [
                    el.get_text(strip=True)
                    for el in container.find_all(["p", "h1", "h2", "h3", "blockquote"])
                    if len(el.get_text(strip=True)) > 20
                ]
                if len(parts) >= 2:
                    body = "\n\n".join(parts)
                    break

        if not body:
            body = "\n\n".join(
                p.get_text(strip=True) for p in soup.find_all("p")
                if len(p.get_text(strip=True)) > 50
            )

        combined = "\n\n".join(x for x in (title, body) if x)
        if combined.strip():
            packet.text = combined
            packet.metadata["title"] = title
        else:
            packet.metadata["fetch_error"] = (
                "The page was reached but no article text could be extracted from it"
            )
    except Exception as exc:
        packet.metadata["fetch_error"] = f"Could not parse the page: {exc}"


def _from_file(packet: ContentPacket, path: str, content_type: ContentType) -> None:
    if content_type is ContentType.IMAGE:
        packet.frame_paths = [path]
        _ocr(packet, path)
    elif content_type is ContentType.AUDIO:
        packet.audio_path = path
        packet.metadata["transcription"] = "unavailable"
    elif content_type is ContentType.VIDEO:
        _extract_frames(packet, path)
    else:
        _read_document(packet, path)


def _ocr(packet: ContentPacket, path: str) -> None:
    """
    Read text out of an image.

    The reason for the check is that `import pytesseract` succeeds on a
    machine with no OCR installed — it wraps a separate binary. Without
    probing for that binary, a failed OCR produced empty text that looked
    exactly like an image containing no words.
    """
    try:
        import pytesseract
        from PIL import Image
        pytesseract.get_tesseract_version()
    except Exception as exc:
        packet.metadata["ocr"] = f"unavailable: {exc}"
        return

    try:
        extracted = pytesseract.image_to_string(Image.open(path)).strip()
        if extracted:
            packet.text = extracted
            packet.metadata["ocr"] = "ok"
        else:
            packet.metadata["ocr"] = "no text found in image"
    except Exception as exc:
        packet.metadata["ocr"] = f"failed: {exc}"


def _extract_frames(packet: ContentPacket, path: str, max_frames: int = 12) -> None:
    try:
        import cv2
    except Exception as exc:
        packet.metadata["frames"] = f"unavailable: {exc}"
        return

    try:
        capture = cv2.VideoCapture(path)
        total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        if total <= 0:
            packet.metadata["frames"] = "video could not be decoded"
            capture.release()
            return

        step = max(1, total // max_frames)
        out_dir = os.path.join(os.path.dirname(path), "frames")
        os.makedirs(out_dir, exist_ok=True)

        saved = []
        for index in range(0, total, step):
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = capture.read()
            if not ok:
                continue
            frame_path = os.path.join(out_dir, f"{os.path.basename(path)}.{index}.jpg")
            cv2.imwrite(frame_path, frame)
            saved.append(frame_path)
            if len(saved) >= max_frames:
                break
        capture.release()
        packet.frame_paths = saved
        packet.metadata["frames"] = f"{len(saved)} extracted"
    except Exception as exc:
        packet.metadata["frames"] = f"failed: {exc}"


def _read_document(packet: ContentPacket, path: str) -> None:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        try:
            from PyPDF2 import PdfReader
            pages = [p.extract_text() or "" for p in PdfReader(path).pages]
            joined = "\n".join(pages).strip()
            if joined:
                packet.text = joined
                packet.metadata["pdf_pages"] = str(len(pages))
                return
            packet.metadata["pdf"] = "no extractable text (likely a scanned document)"
            return
        except Exception as exc:
            packet.metadata["pdf"] = f"failed: {exc}"
            return

    try:
        with open(path, "rb") as fh:
            packet.text = fh.read().decode("utf-8", errors="ignore").strip() or None
    except Exception as exc:
        packet.metadata["read_error"] = str(exc)
