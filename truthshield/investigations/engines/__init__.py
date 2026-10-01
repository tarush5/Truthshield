"""
Engine registry.

Order matters: the text engine extracts the URLs and claims that the URL and
evidence engines then examine. Engines added in later phases (document,
image, audio, video, transaction) register here and declare, through
`applies_to`, which inputs they handle.
"""

from __future__ import annotations

from typing import List

from truthshield.investigations.engines.base import Engine
from truthshield.investigations.engines.document import DocumentEngine
from truthshield.investigations.engines.evidence import EvidenceEngine
from truthshield.investigations.engines.image import ImageEngine
from truthshield.investigations.engines.text import TextEngine
from truthshield.investigations.engines.url import UrlEngine

# (engine, pipeline stage it runs in)
_MEDIA_ENGINES: List[Engine] = [DocumentEngine(), ImageEngine()]
_ANALYSIS_ENGINES: List[Engine] = [TextEngine(), UrlEngine()]
_EVIDENCE_ENGINES: List[Engine] = [EvidenceEngine()]


def media_engines() -> List[Engine]:
    """File engines: extract text (and file-level signals) before the text engine runs."""
    return list(_MEDIA_ENGINES)


def analysis_engines() -> List[Engine]:
    return list(_ANALYSIS_ENGINES)


def evidence_engines() -> List[Engine]:
    return list(_EVIDENCE_ENGINES)


def catalogue() -> List[dict]:
    return [e.describe() for e in _MEDIA_ENGINES + _ANALYSIS_ENGINES + _EVIDENCE_ENGINES]


__all__ = ["Engine", "analysis_engines", "catalogue", "evidence_engines", "media_engines"]
