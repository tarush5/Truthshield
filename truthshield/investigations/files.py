"""
File intake: everything that happens to an upload before any parser sees it.

    stream to a temp file under a size cap → hash while streaming →
    sniff the magic bytes → require the extension to agree → move into
    content-addressed storage → delete the temp file on every failure path

The file's own claim about its type (extension, Content-Type header) is
never trusted on its own: a `.pdf` must begin with `%PDF-`, a `.png` with the
PNG signature. Uploaded files are only ever parsed, never executed.
"""

from __future__ import annotations

import hashlib
import os
import re
import unicodedata
import uuid
from dataclasses import dataclass
from typing import Optional

# kind -> (mime type, extensions, magic-byte check)
FORMATS = {
    "pdf": ("application/pdf", (".pdf",), lambda h: h.startswith(b"%PDF-")),
    "png": ("image/png", (".png",), lambda h: h.startswith(b"\x89PNG\r\n\x1a\n")),
    "jpeg": ("image/jpeg", (".jpg", ".jpeg"), lambda h: h.startswith(b"\xff\xd8\xff")),
    "webp": ("image/webp", (".webp",), lambda h: h[:4] == b"RIFF" and h[8:12] == b"WEBP"),
}
INVESTIGATION_TYPE = {"pdf": "document", "png": "image", "jpeg": "image", "webp": "image"}


class FileRejected(ValueError):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


@dataclass
class StoredFile:
    key: str
    sha256: str
    size: int
    kind: str
    mime_type: str
    filename: str

    @property
    def investigation_type(self) -> str:
        return INVESTIGATION_TYPE[self.kind]


def safe_filename(name: Optional[str]) -> str:
    """A display name only -- never used to build a path."""
    base = os.path.basename((name or "").replace("\\", "/"))
    base = "".join(ch for ch in unicodedata.normalize("NFKC", base) if ch.isprintable())
    base = re.sub(r"\s+", " ", base).strip(" .")
    return base[:120] or "upload"


def sniff(head: bytes) -> Optional[str]:
    for kind, (_, _, check) in FORMATS.items():
        if check(head):
            return kind
    return None


async def receive(upload, *, max_bytes: int) -> StoredFile:
    """Stream an UploadFile into storage, or raise FileRejected (temp file removed)."""
    from truthshield.storage import get_storage

    storage = get_storage()
    filename = safe_filename(getattr(upload, "filename", None))
    ext = os.path.splitext(filename)[1].lower()
    allowed = {e: k for k, (_, exts, _) in FORMATS.items() for e in exts}
    if ext not in allowed:
        raise FileRejected(415, "UNSUPPORTED_FILE",
                           "Unsupported file type. Upload a PDF, PNG, JPEG or WebP file.")

    temp = storage.temp_path(uuid.uuid4().hex)
    digest = hashlib.sha256()
    size, head = 0, b""
    try:
        with open(temp, "wb") as out:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise FileRejected(413, "PAYLOAD_TOO_LARGE",
                                       f"File exceeds the {max_bytes // (1024 * 1024)} MB limit.")
                if len(head) < 16:
                    head += chunk[: 16 - len(head)]
                digest.update(chunk)
                out.write(chunk)
        if size == 0:
            raise FileRejected(400, "BAD_REQUEST", "The uploaded file is empty.")

        kind = sniff(head)
        if kind is None or kind != allowed[ext]:
            raise FileRejected(415, "UNSUPPORTED_FILE",
                               "The file's contents do not match its extension, so it was not accepted.")

        sha = digest.hexdigest()
        storage.put(temp, sha)
        return StoredFile(key=sha, sha256=sha, size=size, kind=kind,
                          mime_type=FORMATS[kind][0], filename=filename)
    except BaseException:
        try:
            os.remove(temp)
        except FileNotFoundError:
            pass
        raise
