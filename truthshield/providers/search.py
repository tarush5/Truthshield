"""
Search providers.

`MultiSourceSearch` wraps the 1.x `EvidenceRetriever`, which already fans out
across every configured engine (Google CSE, Brave, SerpAPI, Fact Check Tools,
news APIs) and the keyless fallbacks, with its own measured query
formulation and caching. Wrapping it rather than re-implementing it keeps
those fixes; new providers implement `BaseSearchProvider` directly.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List
from urllib.parse import urlparse

from truthshield.providers.base import BaseSearchProvider, SearchHit


class NullSearchProvider(BaseSearchProvider):
    name = "none"

    def __init__(self, reason: str):
        self.reason = reason

    @property
    def available(self) -> bool:
        return False

    async def search(self, query: str, *, limit: int = 12) -> List[SearchHit]:
        return []


class MultiSourceSearch(BaseSearchProvider):
    name = "multi-source"

    @property
    def available(self) -> bool:
        return True

    async def search(self, query: str, *, limit: int = 12) -> List[SearchHit]:
        from truthshield.domain.verdict.legacy_types import Claim
        from truthshield.infra.evidence.retriever import EvidenceRetriever

        items = await EvidenceRetriever().retrieve(Claim(text=query))
        hits = []
        for item in items[:limit]:
            publisher = item.source_domain or item.url
            host = urlparse(publisher).hostname if "://" in publisher else publisher.split("/")[0]
            hits.append(SearchHit(
                title=item.title,
                url=item.url,
                snippet=item.snippet or "",
                publisher=(host or "").lower().removeprefix("www."),
                credibility=float(item.source_score),
                provider=self.name,
            ))
        return hits


@lru_cache
def get_search_provider() -> BaseSearchProvider:
    from truthshield.settings import get_settings

    s = get_settings()
    if s.OFFLINE_MODE or not s.EVIDENCE_RETRIEVAL_ENABLED or not s.RAG_LIVE_SEARCH:
        return NullSearchProvider("Live search is disabled (offline mode or configuration).")
    return MultiSourceSearch()


def reset_search_provider() -> None:
    get_search_provider.cache_clear()
