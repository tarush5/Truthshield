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
from truthshield.investigations.engines.evidence import EvidenceEngine
from truthshield.investigations.engines.text import TextEngine
from truthshield.investigations.engines.url import UrlEngine

# (engine, pipeline stage it runs in)
_ANALYSIS_ENGINES: List[Engine] = [TextEngine(), UrlEngine()]
_EVIDENCE_ENGINES: List[Engine] = [EvidenceEngine()]


def analysis_engines() -> List[Engine]:
    return list(_ANALYSIS_ENGINES)


def evidence_engines() -> List[Engine]:
    return list(_EVIDENCE_ENGINES)


def catalogue() -> List[dict]:
    return [e.describe() for e in _ANALYSIS_ENGINES + _EVIDENCE_ENGINES]


__all__ = ["Engine", "analysis_engines", "catalogue", "evidence_engines"]
