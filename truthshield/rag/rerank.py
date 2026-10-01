"""
Reranking.

Retrieval casts a wide net (RRF over semantic and keyword lists); the
reranker orders that net for the claim. Two implementations:

* `CrossEncoderReranker` -- a learned relevance model (e.g.
  `cross-encoder/ms-marco-MiniLM-L-6-v2`), used only when `RERANKER_MODEL`
  names one that loads.
* `FeatureReranker` -- a transparent weighted score over the retrieval
  signals plus source credibility and recency. Not learned; every component
  is returned so the UI can show why a passage ranked where it did.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from functools import lru_cache
from typing import List, Sequence

from truthshield.rag.store import Candidate

logger = logging.getLogger(__name__)

WEIGHTS = {"relevance": 0.55, "keyword": 0.20, "credibility": 0.15, "recency": 0.10}
RECENCY_HALF_LIFE_DAYS = 365.0


def _recency(c: Candidate) -> float:
    stamp = c.published_at or c.retrieved_at
    if stamp is None:
        return 0.5
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    days = max(0.0, (datetime.now(timezone.utc) - stamp).total_seconds() / 86400)
    return 0.5 ** (days / RECENCY_HALF_LIFE_DAYS)


class FeatureReranker:
    name = "feature-weighted-v1"
    learned = False

    def rerank(self, query: str, candidates: Sequence[Candidate]) -> List[dict]:
        if not candidates:
            return []
        max_kw = max(c.keyword for c in candidates) or 1.0
        out = []
        for c in candidates:
            components = {
                "relevance": max(0.0, c.semantic),
                "keyword": c.keyword / max_kw,
                "credibility": c.credibility,
                "recency": _recency(c),
            }
            score = sum(WEIGHTS[k] * v for k, v in components.items())
            out.append({"candidate": c, "score": round(score, 4), "components": {k: round(v, 3) for k, v in components.items()}})
        return sorted(out, key=lambda r: -r["score"])


class CrossEncoderReranker:
    learned = True

    def __init__(self, model_name: str):
        from sentence_transformers import CrossEncoder

        from truthshield.settings import get_settings
        self.name = model_name
        self._model = CrossEncoder(model_name, cache_folder=str(get_settings().MODEL_CACHE_DIR))

    def rerank(self, query: str, candidates: Sequence[Candidate]) -> List[dict]:
        if not candidates:
            return []
        logits = self._model.predict([(query, c.text) for c in candidates], show_progress_bar=False)
        out = []
        for c, logit in zip(candidates, logits):
            relevance = 1.0 / (1.0 + math.exp(-float(logit)))
            score = 0.85 * relevance + 0.15 * c.credibility
            out.append({"candidate": c, "score": round(score, 4),
                        "components": {"relevance": round(relevance, 3), "credibility": round(c.credibility, 3)}})
        return sorted(out, key=lambda r: -r["score"])


@lru_cache
def get_reranker():
    from truthshield.settings import get_settings

    name = get_settings().RERANKER_MODEL.strip()
    if name:
        try:
            return CrossEncoderReranker(name)
        except Exception as exc:
            logger.warning("Reranker %s unavailable (%s); using the feature reranker", name, type(exc).__name__)
    return FeatureReranker()
