"""
Retrieval-augmented evidence gathering.

    claim → query expansion → hybrid search of the evidence store
          → (too little local evidence?) live search → ingest → search again
          → metadata filters → rerank → passage extraction

The result is a `Retrieval`: the passages, plus every number that decided
their order and a record of what was and was not consulted. Adjudication
(stance, verdict) happens downstream on these passages; nothing here decides
whether a claim is true.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from truthshield.providers.base import BaseEmbeddingModel, BaseSearchProvider
from truthshield.rag.store import Candidate, EvidenceStore, Filters
from truthshield.rag.text import best_passage, expand_query

logger = logging.getLogger(__name__)

# Similarity above which a stored chunk counts as "about" the claim, by
# embedding kind. Semantic: the 1.x measured floor (on-topic items scored
# 0.40-0.81 on the benchmark fixture). Lexical vectors score lower for the
# same overlap, so their floor is lower; keyword matches always count.
RELEVANCE_FLOOR = {"semantic": 0.40, "lexical": 0.15}


@dataclass
class Retrieval:
    claim: str
    variants: List[Tuple[str, str]]
    embedding: Dict[str, str]
    reranker: str
    filters: dict
    local_relevant_before: int = 0
    live_search: str = "not_needed"          # not_needed | used | unavailable | failed
    live_hits: int = 0
    ingested: int = 0
    live_detail: Optional[str] = None
    candidates: int = 0
    passages: List[dict] = field(default_factory=list)
    # Stored text of each cited chunk, for citation checks. Not serialised.
    chunk_texts: Dict[str, str] = field(default_factory=dict)

    def diagnostics(self) -> dict:
        return {
            "query_variants": [{"strategy": s, "query": q} for s, q in self.variants],
            "embedding": self.embedding,
            "reranker": self.reranker,
            "filters": self.filters,
            "local_relevant_before": self.local_relevant_before,
            "live_search": self.live_search,
            "live_hits": self.live_hits,
            "ingested": self.ingested,
            "live_detail": self.live_detail,
            "candidates": self.candidates,
            "passages": len(self.passages),
        }


class RAGEngine:
    def __init__(
        self,
        session: Session,
        *,
        embedder: Optional[BaseEmbeddingModel] = None,
        search: Optional[BaseSearchProvider] = None,
        reranker=None,
        filters: Optional[Filters] = None,
        top_k: Optional[int] = None,
        min_local_hits: Optional[int] = None,
    ):
        from truthshield.providers import get_embedding_model, get_search_provider
        from truthshield.rag.rerank import get_reranker
        from truthshield.settings import get_settings

        settings = get_settings()
        self.embedder = embedder or get_embedding_model()
        self.search_provider = search or get_search_provider()
        self.reranker = reranker or get_reranker()
        self.filters = filters or Filters()
        self.top_k = top_k or settings.RAG_TOP_K
        self.min_local_hits = settings.RAG_LOCAL_MIN_HITS if min_local_hits is None else min_local_hits
        self.store = EvidenceStore(session, self.embedder)

    def _relevant(self, candidates: List[Candidate]) -> List[Candidate]:
        floor = RELEVANCE_FLOOR.get(self.embedder.kind, 0.4)
        return [c for c in candidates if c.semantic >= floor or c.keyword > 0]

    def _search_variants(self, variants: List[Tuple[str, str]]) -> List[Candidate]:
        merged: Dict[str, Candidate] = {}
        for strategy, query in variants:
            for cand in self.store.search(query, filters=self.filters, limit=30):
                existing = merged.get(cand.chunk_id)
                if existing is None:
                    cand.matched_by = [f"{m}:{strategy}" for m in cand.matched_by]
                    merged[cand.chunk_id] = cand
                else:
                    existing.rrf += cand.rrf
                    existing.semantic = max(existing.semantic, cand.semantic)
                    existing.keyword = max(existing.keyword, cand.keyword)
                    existing.matched_by += [f"{m}:{strategy}" for m in cand.matched_by]
        return sorted(merged.values(), key=lambda c: -c.rrf)

    async def retrieve(self, claim: str) -> Retrieval:
        return (await self.retrieve_many([claim]))[0]

    async def retrieve_many(self, claims: List[str]) -> List[Retrieval]:
        """
        Retrieve for several claims at once.

        The live searches are the slow, network-bound part, so the ones that
        are needed run concurrently. Everything that touches the database
        (search, ingestion, rerank) stays sequential on the one session:
        a SQLAlchemy session must not be shared across concurrent work.
        """
        import asyncio

        retrievals: List[Retrieval] = []
        candidates_by_claim: List[List[Candidate]] = []
        for claim in claims:
            variants = expand_query(claim)
            retrieval = Retrieval(
                claim=claim,
                variants=variants,
                embedding={"model": self.embedder.name, "kind": self.embedder.kind},
                reranker=self.reranker.name,
                filters=self.filters.as_dict(),
            )
            candidates = self._search_variants(variants)
            retrieval.local_relevant_before = len(self._relevant(candidates))
            retrievals.append(retrieval)
            candidates_by_claim.append(candidates)

        needs_live = [i for i, r in enumerate(retrievals) if r.local_relevant_before < self.min_local_hits]
        if needs_live and not self.search_provider.available:
            for i in needs_live:
                retrievals[i].live_search = "unavailable"
                retrievals[i].live_detail = getattr(self.search_provider, "reason", "No live search provider.")
        elif needs_live:
            results = await asyncio.gather(
                *(self.search_provider.search(retrievals[i].claim, limit=15) for i in needs_live),
                return_exceptions=True,
            )
            for i, hits in zip(needs_live, results):
                retrieval = retrievals[i]
                if isinstance(hits, BaseException):
                    # Never replaced with anything invented: the claim is
                    # assessed on whatever the store already held.
                    retrieval.live_search = "failed"
                    retrieval.live_detail = f"Evidence unavailable from the search provider ({type(hits).__name__})."
                    logger.warning("Live search failed: %s", hits)
                    continue
                retrieval.live_search = "used"
                retrieval.live_hits = len(hits)
                self._ingest(retrieval, hits)
                candidates_by_claim[i] = self._search_variants(retrieval.variants)

        for retrieval, candidates in zip(retrievals, candidates_by_claim):
            self._finish(retrieval, candidates)
        return retrievals

    def _ingest(self, retrieval: Retrieval, hits) -> None:
        for hit in hits:
            if not (hit.snippet or hit.title):
                continue
            try:
                _, created = self.store.ingest(
                    url=hit.url, title=hit.title, content=hit.snippet or hit.title,
                    provider=hit.provider or self.search_provider.name,
                    content_scope="snippet", credibility_prior=hit.credibility,
                    publisher=hit.publisher or None,
                )
                retrieval.ingested += int(created)
            except Exception as exc:
                self.store.session.rollback()
                logger.debug("Skipped ingesting %s: %s", hit.url, exc)

    def _finish(self, retrieval: Retrieval, candidates: List[Candidate]) -> None:
        claim = retrieval.claim
        relevant = self._relevant(candidates)
        retrieval.candidates = len(relevant)
        for ranked in self.reranker.rerank(claim, relevant)[: self.top_k]:
            c: Candidate = ranked["candidate"]
            retrieval.passages.append({
                "document_id": c.document_id,
                "chunk_id": c.chunk_id,
                "title": c.title,
                "url": c.url,
                "publisher": c.publisher,
                "category": c.category,
                "credibility": round(c.credibility, 2),
                "content_scope": c.content_scope,
                "published_at": c.published_at.isoformat() if c.published_at else None,
                "retrieved_at": c.retrieved_at.isoformat() if c.retrieved_at else None,
                "passage": best_passage(claim, c.text),
                "scores": {
                    "final": ranked["score"],
                    "components": ranked["components"],
                    "semantic": round(c.semantic, 3),
                    "keyword": round(c.keyword, 3),
                    "rrf": round(c.rrf, 4),
                    "matched_by": sorted(set(c.matched_by)),
                },
            })
