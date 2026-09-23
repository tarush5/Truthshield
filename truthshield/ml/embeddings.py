"""
Sentence embeddings — semantic relevance and retrieval.

Used for three things:

  1. **Ranking evidence.** Lexical overlap cannot tell that an article about
     the shape of the Earth addresses a flat-Earth claim when it shares no
     distinctive words with it.

  2. **Not filtering.** Dropping off-topic results by cosine distance is the
     obvious next step and it was measured and rejected: on the benchmark
     fixture a 0.40 floor turned a correct verdict into an abstention
     (9/0/3 -> 8/0/4) and a 0.45 floor produced a wrong one. Genuinely
     on-topic evidence sits closer to the junk than it looks. `rank()`
     therefore exists and is used for ordering; nothing calls it to discard.

  3. **A semantic cache.** Two submissions of the same claim in different
     wording are the same question. Keying the cache on the exact string
     missed that entirely.

Loading is lazy and failure is permanent-per-process: a missing dependency is
not re-attempted on every request, which is what made the old optional-import
pattern re-run the import machinery and re-log the same warning each time.
"""

from __future__ import annotations

import logging
import threading
from typing import List, Optional, Sequence, Tuple

from truthshield.settings import get_settings

logger = logging.getLogger(__name__)

# Small, fast, and good enough for sentence-level similarity. A larger model
# costs more load time and memory than the ranking gain justifies here.
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Below this cosine similarity, evidence is not about the claim. Chosen from
# the fixture: genuinely on-topic items scored 0.40–0.81, while unrelated
# results that shared vocabulary ("NASA has quietly accumulated 150
# petabytes…" against a flat-Earth claim) sat at 0.38 and below.
RELEVANCE_FLOOR = 0.40

# Two phrasings of the same claim. Deliberately strict: a false hit here
# serves a stale verdict for a question nobody asked.
SAME_CLAIM = 0.92


class Embedder:
    """Lazily-loaded sentence encoder. Safe to call when unavailable."""

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model_name = model_name
        self._model = None
        self._error: Optional[str] = None
        self._attempted = False
        self._lock = threading.Lock()

    # ──────────────────────────────────────────────────────────

    def _load(self) -> None:
        if self._attempted:
            return
        with self._lock:
            if self._attempted:
                return
            self._attempted = True

            if not get_settings().ENABLE_ML_DETECTORS:
                self._error = "ENABLE_ML_DETECTORS is false"
                return
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(
                    self.model_name,
                    cache_folder=str(get_settings().MODEL_CACHE_DIR),
                )
                logger.info("Embedding model ready: %s", self.model_name)
            except Exception as exc:
                self._error = f"{type(exc).__name__}: {exc}"
                logger.info(
                    "Embeddings unavailable (%s). Relevance falls back to "
                    "lexical overlap.", self._error,
                )

    @property
    def available(self) -> bool:
        self._load()
        return self._model is not None

    @property
    def error(self) -> Optional[str]:
        self._load()
        return self._error

    # ──────────────────────────────────────────────────────────

    def encode(self, texts: Sequence[str]):
        """
        Encode to L2-normalised vectors, or None when unavailable.

        Normalised so that a dot product *is* cosine similarity — one matrix
        multiply instead of a per-pair norm.
        """
        if not self.available or not texts:
            return None
        try:
            return self._model.encode(
                list(texts),
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
                # Batched in one forward pass: per-item encoding of 15
                # snippets costs several times this.
                batch_size=32,
            )
        except Exception as exc:
            logger.warning("Encoding failed: %s", exc)
            return None

    def similarities(self, query: str, documents: Sequence[str]) -> Optional[List[float]]:
        """Cosine similarity of `query` against each document, or None."""
        if not documents:
            return []
        vectors = self.encode([query, *documents])
        if vectors is None:
            return None
        import numpy as np
        return np.dot(vectors[1:], vectors[0]).tolist()

    def rank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        floor: float = RELEVANCE_FLOOR,
        top_k: Optional[int] = None,
    ) -> Optional[List[Tuple[int, float]]]:
        """
        Indices of the documents that are about `query`, best first.

        Returns None — not an empty list — when the model is unavailable, so
        callers can tell "nothing was relevant" from "nothing was checked".
        """
        scores = self.similarities(query, documents)
        if scores is None:
            return None
        ranked = sorted(
            ((i, s) for i, s in enumerate(scores) if s >= floor),
            key=lambda pair: pair[1],
            reverse=True,
        )
        return ranked[:top_k] if top_k else ranked

    def same_claim(self, a: str, b: str, threshold: float = SAME_CLAIM) -> bool:
        """Whether two strings are the same claim in different words."""
        scores = self.similarities(a, [b])
        return bool(scores) and scores[0] >= threshold


class EmbeddingIndex:
    """
    A small in-memory vector index.

    Deliberately brute force: these sets are tens of vectors, where a numpy
    dot product is faster than any index structure and needs no extra
    service. A vector database here would be infrastructure without a
    workload.
    """

    def __init__(self, embedder: Optional[Embedder] = None):
        self._embedder = embedder or get_embedder()
        self._texts: List[str] = []
        self._payloads: List[dict] = []
        self._matrix = None

    def __len__(self) -> int:
        return len(self._texts)

    @property
    def available(self) -> bool:
        return self._embedder.available

    def add(self, texts: Sequence[str], payloads: Sequence[dict]) -> bool:
        """Index a batch. False when embeddings are unavailable."""
        if not self.available or not texts:
            return False
        vectors = self._embedder.encode(texts)
        if vectors is None:
            return False

        import numpy as np
        self._texts.extend(texts)
        self._payloads.extend(payloads)
        self._matrix = vectors if self._matrix is None else np.vstack([self._matrix, vectors])
        return True

    def search(self, query: str, top_k: int = 5, floor: float = RELEVANCE_FLOOR) -> List[dict]:
        """Payloads most similar to `query`, each with its score attached."""
        if self._matrix is None or not self.available:
            return []
        vector = self._embedder.encode([query])
        if vector is None:
            return []

        import numpy as np
        scores = np.dot(self._matrix, vector[0])
        order = np.argsort(-scores)[:top_k]
        return [
            {**self._payloads[i], "similarity": float(scores[i])}
            for i in order
            if scores[i] >= floor
        ]


_embedder: Optional[Embedder] = None
_embedder_lock = threading.Lock()


def get_embedder() -> Embedder:
    """The process-wide encoder. Loading it twice would double the memory."""
    global _embedder
    if _embedder is None:
        with _embedder_lock:
            if _embedder is None:
                _embedder = Embedder()
    return _embedder
