"""
Object storage for uploaded files.

Content-addressed: a file is stored under its SHA-256, so the same upload
twice is stored once, and a key can never be made to point at a path outside
the storage root (keys are validated hex digests, not user-supplied names).

`LocalStorage` writes to `STORAGE_DIR`. The interface is what an
S3-compatible backend implements when media arrives in Phase 3.
"""

from __future__ import annotations

import os
import re
import shutil
from functools import lru_cache
from pathlib import Path

_KEY = re.compile(r"^[0-9a-f]{64}$")


class StorageError(RuntimeError):
    pass


class LocalStorage:
    name = "local"

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "tmp").mkdir(exist_ok=True)

    def path_for(self, key: str) -> Path:
        if not _KEY.match(key or ""):
            raise StorageError("invalid storage key")
        path = (self.root / key[:2] / key[2:4] / key).resolve()
        if self.root not in path.parents:
            raise StorageError("storage key escapes the storage root")
        return path

    def temp_path(self, name: str) -> Path:
        if not re.match(r"^[0-9a-f]{32}$", name):
            raise StorageError("invalid temporary name")
        return self.root / "tmp" / name

    def put(self, temp: Path, key: str) -> str:
        """Move a fully written temp file into place under its digest."""
        target = self.path_for(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            os.remove(temp)                     # identical content already stored
        else:
            shutil.move(str(temp), str(target))
        return key

    def exists(self, key: str) -> bool:
        return self.path_for(key).exists()

    def delete(self, key: str) -> None:
        try:
            os.remove(self.path_for(key))
        except FileNotFoundError:
            pass


@lru_cache
def get_storage() -> LocalStorage:
    from truthshield.settings import get_settings

    settings = get_settings()
    if settings.STORAGE_BACKEND != "local":
        raise StorageError(f"Unsupported STORAGE_BACKEND: {settings.STORAGE_BACKEND}")
    return LocalStorage(settings.STORAGE_DIR)
