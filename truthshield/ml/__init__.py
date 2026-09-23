"""
Optional local inference.

Both models are off by default (`ENABLE_ML_DETECTORS`), and both are here on
measured terms rather than because they are fashionable. The measurement is
the frozen benchmark fixture in `tests/fixtures/`; `.lab/sweep.py` reproduces
it.

  embeddings  (all-MiniLM-L6-v2, 384-dim)
      Ranks evidence by meaning instead of shared words, which is how a piece
      titled "The Photos That Shaped Our Understanding of Earth's Shape" ends
      up first on a flat-Earth claim where lexical overlap buried it mid-pack
      at 0.20. It reorders what the reader sees first and keys the semantic
      cache. It does **not** change verdicts: used as a relevance filter it
      was neutral at best (9/0/3 unfiltered, 8/0/4 at a 0.40 floor), so it
      ranks and does not discard.

  nli         (nli-deberta-v3-xsmall)
      Stance, restricted to refutation above 0.98 confidence. Unrestricted it
      cost four verdicts on the fixture by reading the refutational *form* of
      fact-check headlines as a verdict on any claim. See `nli.py` -- the
      docstring there carries the full numbers and is worth reading before
      touching the thresholds.

Neither resolves the fixture's three abstentions. Those are a retrieval
problem: on the flat-Earth claim roughly three of fourteen retrieved items
are on topic at all.

With neither installed the system falls back to the lexical path it has
always had, and `availability()` reports which are live so a report can say
what it actually used.
"""

from truthshield.ml.embeddings import EmbeddingIndex, get_embedder
from truthshield.ml.nli import StanceLabel, get_stance_model

__all__ = [
    "EmbeddingIndex",
    "StanceLabel",
    "get_embedder",
    "get_stance_model",
    "availability",
]


def availability() -> dict:
    """Which inference paths can actually run, for /health and the report."""
    embedder = get_embedder()
    stance = get_stance_model()
    return {
        "embeddings": {
            "available": embedder.available,
            "model": embedder.model_name if embedder.available else None,
            "detail": embedder.error,
        },
        "stance_nli": {
            "available": stance.available,
            "model": stance.model_name if stance.available else None,
            "detail": stance.error,
        },
    }
