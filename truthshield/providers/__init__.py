"""
Swappable external capabilities: LLM, search, embeddings, OCR.

Each `get_*` returns the configured provider, or an explicitly unavailable
one carrying the reason -- never a stand-in that fabricates output.
"""

from truthshield.providers.base import (
    BaseEmbeddingModel, BaseLLMProvider, BaseOCRProvider, BaseSearchProvider,
    LLMResult, OCRResult, OCRWord, SearchHit,
)
from truthshield.providers.embeddings import get_embedding_model
from truthshield.providers.llm import get_llm_provider
from truthshield.providers.ocr import get_ocr_provider
from truthshield.providers.search import get_search_provider


def status() -> dict:
    """What each provider slot resolves to, for /system/health."""
    from truthshield.providers.resilience import all_breakers

    llm = get_llm_provider()
    emb = get_embedding_model()
    ocr = get_ocr_provider()
    search = get_search_provider()
    return {
        "llm": {"provider": llm.name, "model": llm.model or None, "available": llm.available,
                "detail": llm.unavailable_reason},
        "embeddings": {"provider": emb.name, "kind": emb.kind, "dim": emb.dim},
        "ocr": {"provider": ocr.name, "available": ocr.available, "detail": ocr.unavailable_reason},
        "search": {"provider": search.name, "available": search.available,
                   "detail": getattr(search, "reason", None)},
        "circuit_breakers": all_breakers(),
    }


def reset_all() -> None:
    """Drop cached provider choices (tests vary settings)."""
    from truthshield.providers.embeddings import reset_embedding_model
    from truthshield.providers.llm import reset_llm_provider
    from truthshield.providers.ocr import reset_ocr_provider
    from truthshield.providers.search import reset_search_provider

    reset_llm_provider()
    reset_embedding_model()
    reset_ocr_provider()
    reset_search_provider()


__all__ = [
    "BaseEmbeddingModel", "BaseLLMProvider", "BaseOCRProvider", "BaseSearchProvider",
    "LLMResult", "OCRResult", "OCRWord", "SearchHit",
    "get_embedding_model", "get_llm_provider", "get_ocr_provider", "get_search_provider",
    "reset_all", "status",
]
