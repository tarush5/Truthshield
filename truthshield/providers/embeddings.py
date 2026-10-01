"""
Embedding models.

Two implementations behind one interface:

* `SentenceTransformerEmbedding` -- all-MiniLM-L6-v2, a trained semantic
  model (384-dim). Needs the ML extras and `ENABLE_ML_DETECTORS=true`.
* `HashingEmbedding` -- signed feature hashing of word unigrams and bigrams
  into the same 384 dimensions. Deterministic and dependency-free, so the
  vector store works on a bare install. It measures **shared vocabulary**, not
  meaning, and is labelled `kind="lexical"` everywhere a score is shown.

Vectors from different models are never compared: every stored vector
carries the model name, and search filters on it.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from functools import lru_cache
from typing import List, Sequence

from truthshield.providers.base import BaseEmbeddingModel

DIM = 384
_WORD = re.compile(r"[^\W_]+", re.UNICODE)

# Small, language-agnostic stoplist: these carry no topical signal and would
# otherwise dominate lexical vectors.
_STOP = frozenset("""
a an and are as at be but by for from has have he her his i in is it its of on or our she that the their them
they this to was we were what when which who will with you your not no do does did can could would should
""".split())


class HashingEmbedding(BaseEmbeddingModel):
    name = "hashing-ngram-v1"
    dim = DIM
    kind = "lexical"

    @property
    def available(self) -> bool:
        return True

    @staticmethod
    def _features(text: str) -> Counter:
        words = [w for w in _WORD.findall(text.lower()) if w not in _STOP]
        grams = words + [f"{a}_{b}" for a, b in zip(words, words[1:])]
        return Counter(grams)

    def _vector(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        for gram, count in self._features(text).items():
            digest = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "little") % self.dim
            sign = 1.0 if digest[4] & 1 else -1.0
            # Sublinear term frequency; bigrams weigh a little more (phrases).
            vec[index] += sign * (1.0 + math.log(count)) * (1.3 if "_" in gram else 1.0)
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        return [self._vector(t or "") for t in texts]


class SentenceTransformerEmbedding(BaseEmbeddingModel):
    name = "sentence-transformers/all-MiniLM-L6-v2"
    dim = DIM
    kind = "semantic"

    def __init__(self):
        from truthshield.ml.embeddings import get_embedder
        self._embedder = get_embedder()

    @property
    def available(self) -> bool:
        return self._embedder.available

    @property
    def unavailable_reason(self):
        return self._embedder.error

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        vectors = self._embedder.encode(list(texts))
        if vectors is None:
            raise RuntimeError("Semantic embedding model is unavailable")
        return [list(map(float, v)) for v in vectors]


@lru_cache
def get_embedding_model() -> BaseEmbeddingModel:
    from truthshield.settings import get_settings

    choice = get_settings().EMBEDDING_PROVIDER.strip().lower()
    if choice == "hashing":
        return HashingEmbedding()
    semantic = SentenceTransformerEmbedding()
    if choice == "sentence-transformers" or semantic.available:
        return semantic
    return HashingEmbedding()


def reset_embedding_model() -> None:
    get_embedding_model.cache_clear()
