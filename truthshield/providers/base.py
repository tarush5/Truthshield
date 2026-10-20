"""
Provider interfaces.

Every external capability -- language model, web search, embeddings, OCR --
sits behind one of these, so a provider can be swapped by configuration and
the rest of the system never learns which one answered. Each provider says
whether it is available and why not, because "the check could not run" must
never be reported as "the check found nothing".
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import List, Optional, Sequence


# ── Language models ───────────────────────────────────────────

@dataclass
class LLMResult:
    text: Optional[str]
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    refused: bool = False
    detail: Optional[str] = None
    # The output hit the token limit and stopped mid-answer.
    truncated: bool = False

    @property
    def ok(self) -> bool:
        return bool(self.text) and not self.refused


class BaseLLMProvider(abc.ABC):
    name: str = "llm"

    @property
    @abc.abstractmethod
    def available(self) -> bool: ...

    @property
    def unavailable_reason(self) -> Optional[str]:
        return None

    @property
    @abc.abstractmethod
    def model(self) -> str: ...

    @abc.abstractmethod
    def complete(self, *, system: str, prompt: str, max_tokens: int = 4000) -> LLMResult:
        """One bounded completion. Never raises for provider errors."""


# ── Search ────────────────────────────────────────────────────

@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str
    publisher: str = ""
    credibility: float = 0.5          # the provider's own prior, 0-1
    published_at: Optional[str] = None
    provider: str = ""


class BaseSearchProvider(abc.ABC):
    name: str = "search"

    @property
    @abc.abstractmethod
    def available(self) -> bool: ...

    @abc.abstractmethod
    async def search(self, query: str, *, limit: int = 12) -> List[SearchHit]: ...


# ── Embeddings ────────────────────────────────────────────────

class BaseEmbeddingModel(abc.ABC):
    name: str = "embedding"
    dim: int = 384
    #: "semantic" (a trained sentence model) or "lexical" (token hashing).
    #: Shown wherever similarity scores are, because they mean different things.
    kind: str = "semantic"

    @property
    @abc.abstractmethod
    def available(self) -> bool: ...

    @abc.abstractmethod
    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        """L2-normalised vectors, one per text, so dot product = cosine."""


# ── OCR ───────────────────────────────────────────────────────

@dataclass
class OCRWord:
    text: str
    confidence: float                 # 0-100 as the engine reports it
    bbox: List[int]                   # [left, top, width, height]


@dataclass
class OCRResult:
    text: str
    words: List[OCRWord] = field(default_factory=list)
    languages: str = ""
    engine: str = ""

    @property
    def mean_confidence(self) -> Optional[float]:
        scored = [w.confidence for w in self.words if w.confidence >= 0]
        return round(sum(scored) / len(scored), 1) if scored else None


class BaseOCRProvider(abc.ABC):
    name: str = "ocr"

    @property
    @abc.abstractmethod
    def available(self) -> bool: ...

    @property
    def unavailable_reason(self) -> Optional[str]:
        return None

    @abc.abstractmethod
    def recognize(self, image, *, languages: Optional[str] = None) -> OCRResult:
        """`image` is a PIL image. Raises when OCR itself fails."""
