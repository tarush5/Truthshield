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


def warm_engines() -> float:
    """
    Pay the one-off costs (imports, language profiles, detector registries,
    the embedding model and the adjudicator) before the first real request.

    Runs a synthetic sample through the text and URL engines and initialises
    the evidence path without searching. Never touches the network or the
    database. Returns the time it took in milliseconds.
    """
    import hashlib
    import time

    from truthshield.investigations.types import InvestigationContext, InvestigationType

    started = time.perf_counter()
    sample = "Warm-up: your account will be blocked today, verify at https://example.com/login now."
    ctx = InvestigationContext(
        investigation_id="warmup", type=InvestigationType.MESSAGE, content=sample, text=sample,
        input_sha256=hashlib.sha256(sample.encode()).hexdigest(), allow_page_fetch=False,
    )
    text, url = _ANALYSIS_ENGINES
    ctx.artifacts.update(text.run(ctx).artifacts)
    url.run(ctx)

    from truthshield.investigations.engines.evidence import DeterministicAdjudicator
    from truthshield.providers import get_embedding_model

    get_embedding_model().embed(["warm-up"])
    DeterministicAdjudicator()
    return (time.perf_counter() - started) * 1000


def catalogue() -> List[dict]:
    return [e.describe() for e in _MEDIA_ENGINES + _ANALYSIS_ENGINES + _EVIDENCE_ENGINES]


__all__ = ["Engine", "analysis_engines", "catalogue", "evidence_engines", "media_engines", "warm_engines"]
