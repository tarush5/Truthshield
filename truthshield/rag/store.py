"""
The evidence store.

Documents (search results, fetched pages, analyst uploads) are chunked,
embedded and kept, so evidence accumulates instead of being re-searched from
scratch on every request, and every passage an investigation cites has a
stable document and chunk id.

Retrieval is hybrid:

* **semantic** -- cosine similarity of chunk embeddings (pgvector HNSW on
  PostgreSQL; numpy over the candidate set on SQLite);
* **keyword**  -- PostgreSQL full-text rank, or Okapi BM25 on SQLite;

fused with Reciprocal Rank Fusion, which needs no score calibration between
the two lists. Metadata filters (publisher category, credibility floor,
domain allow/deny, publication window) apply to both.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Sequence
from urllib.parse import urlparse, urlunparse

from sqlalchemy import Float, func, select
from sqlalchemy.orm import Session

from truthshield.infra.models import EvidenceChunk, EvidenceDocument, Source
from truthshield.providers.base import BaseEmbeddingModel
from truthshield.rag.text import chunk_text, terms

logger = logging.getLogger(__name__)

RRF_K = 60
CANDIDATES_PER_LIST = 50
SQLITE_SCAN_LIMIT = 20_000


def _now() -> datetime:
    return datetime.now(timezone.utc)


def normalise_url(url: str) -> str:
    """Scheme and host lower-cased, fragment and trailing slash dropped."""
    parsed = urlparse((url or "").strip())
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", parsed.query, ""))


def domain_of(url: str) -> str:
    host = urlparse(url).hostname if "://" in (url or "") else (url or "").split("/")[0]
    return (host or "").lower().removeprefix("www.")


@dataclass
class Filters:
    categories: Optional[Sequence[str]] = None
    min_credibility: Optional[float] = None
    include_domains: Optional[Sequence[str]] = None
    exclude_domains: Optional[Sequence[str]] = None
    published_after: Optional[datetime] = None
    published_before: Optional[datetime] = None

    def as_dict(self) -> dict:
        return {k: (v.isoformat() if isinstance(v, datetime) else v)
                for k, v in self.__dict__.items() if v not in (None, [], ())}


@dataclass
class Candidate:
    chunk_id: str
    document_id: str
    text: str
    title: str
    url: str
    publisher: str
    category: str
    credibility: float
    published_at: Optional[datetime]
    retrieved_at: Optional[datetime]
    content_scope: str
    semantic: float = 0.0
    keyword: float = 0.0
    rrf: float = 0.0
    matched_by: List[str] = field(default_factory=list)


class EvidenceStore:
    def __init__(self, session: Session, embedder: BaseEmbeddingModel):
        self.session = session
        self.embedder = embedder
        # SQLite only: the scanned corpus, kept for the life of this store
        # (one request) and dropped on ingest. Every claim searches several
        # query variants, and reloading and re-tokenising up to 20k chunks for
        # each one was the dominant cost of a local evidence check.
        self._corpora: Dict[str, "_Corpus"] = {}

    @property
    def is_postgres(self) -> bool:
        return self.session.get_bind().dialect.name == "postgresql"

    # ── Source registry ───────────────────────────────────────

    def upsert_source(self, domain: str, *, credibility_prior: float = 0.5, name: Optional[str] = None) -> Source:
        from truthshield.investigations.engines.evidence import source_category

        domain = domain or "unknown"
        source = self.session.query(Source).filter(Source.domain == domain).one_or_none()
        if source is None:
            source = Source(
                domain=domain,
                name=name or domain,
                category=source_category(domain, credibility_prior),
                credibility=round(float(credibility_prior), 3),
            )
            self.session.add(source)
            self.session.flush()
        else:
            source.last_seen_at = _now()
            if not source.curated:
                # A running average of the priors providers report; curated
                # entries are an administrator's decision and stay put.
                source.credibility = round(0.8 * source.credibility + 0.2 * float(credibility_prior), 3)
                source.category = source_category(domain, source.credibility)
        return source

    # ── Ingestion ─────────────────────────────────────────────

    def ingest(
        self,
        *,
        url: str,
        title: str,
        content: str,
        provider: str,
        content_scope: str = "snippet",
        credibility_prior: float = 0.5,
        publisher: Optional[str] = None,
        published_at: Optional[datetime] = None,
        meta: Optional[dict] = None,
        ingested_by=None,
    ) -> tuple:
        """Store a document; returns (document, created). Idempotent per URL and content."""
        content = (content or "").strip()
        if not content:
            raise ValueError("empty document")
        url = normalise_url(url)
        url_sha = hashlib.sha256(url.encode("utf-8")).hexdigest()
        content_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        source = self.upsert_source(publisher or domain_of(url), credibility_prior=credibility_prior)

        document = self.session.query(EvidenceDocument).filter(EvidenceDocument.url_sha256 == url_sha).one_or_none()
        if document is not None and document.content_sha256 == content_sha \
                and all(c.embedding_model == self.embedder.name for c in document.chunks):
            document.retrieved_at = _now()
            self.session.commit()
            self._corpora.clear()
            return document, False

        if document is None:
            document = EvidenceDocument(url=url, url_sha256=url_sha)
            self.session.add(document)
        else:
            # delete-orphan cascade removes the rows; clearing the collection
            # keeps the in-memory document consistent with them.
            document.chunks.clear()
            self.session.flush()

        document.source_id = source.id
        document.title = (title or "")[:1000]
        document.content_sha256 = content_sha
        document.content_scope = content_scope
        document.provider = provider
        document.published_at = published_at
        document.retrieved_at = _now()
        document.meta = meta
        document.ingested_by = ingested_by
        self.session.flush()

        pieces = chunk_text(f"{title}. {content}" if title and content_scope == "snippet" else content)
        vectors = self.embedder.embed([p.text for p in pieces])
        for piece, vector in zip(pieces, vectors):
            document.chunks.append(EvidenceChunk(
                chunk_index=piece.index, text=piece.text,
                char_start=piece.start, char_end=piece.end,
                embedding=vector, embedding_model=self.embedder.name,
            ))
        self.session.commit()
        self._corpora.clear()
        return document, True

    # ── Retrieval ─────────────────────────────────────────────

    def _filtered_chunks(self, filters: Filters):
        query = (
            select(EvidenceChunk, EvidenceDocument, Source)
            .join(EvidenceDocument, EvidenceChunk.document_id == EvidenceDocument.id)
            .outerjoin(Source, EvidenceDocument.source_id == Source.id)
            .where(EvidenceChunk.embedding_model == self.embedder.name)
        )
        if filters.categories:
            query = query.where(Source.category.in_(list(filters.categories)))
        if filters.min_credibility is not None:
            query = query.where(Source.credibility >= filters.min_credibility)
        if filters.include_domains:
            query = query.where(Source.domain.in_(list(filters.include_domains)))
        if filters.exclude_domains:
            query = query.where(Source.domain.notin_(list(filters.exclude_domains)))
        if filters.published_after:
            query = query.where(EvidenceDocument.published_at >= filters.published_after)
        if filters.published_before:
            query = query.where(EvidenceDocument.published_at <= filters.published_before)
        return query

    @staticmethod
    def _candidate(chunk: EvidenceChunk, doc: EvidenceDocument, source: Optional[Source]) -> Candidate:
        return Candidate(
            chunk_id=str(chunk.id), document_id=str(doc.id), text=chunk.text,
            title=doc.title or "", url=doc.url,
            publisher=source.domain if source else domain_of(doc.url),
            category=source.category if source else "UNKNOWN",
            credibility=source.credibility if source else 0.5,
            published_at=doc.published_at, retrieved_at=doc.retrieved_at,
            content_scope=doc.content_scope,
        )

    def search(self, query: str, *, filters: Optional[Filters] = None, limit: int = 20) -> List[Candidate]:
        filters = filters or Filters()
        q_vec = self.embedder.embed([query])[0]
        if self.is_postgres:
            semantic, keyword = self._search_postgres(query, q_vec, filters)
        else:
            semantic, keyword = self._search_python(query, q_vec, filters)

        fused: Dict[str, Candidate] = {}
        for label, ranked in (("semantic", semantic), ("keyword", keyword)):
            for rank, cand in enumerate(ranked):
                existing = fused.get(cand.chunk_id)
                if existing is None:
                    fused[cand.chunk_id] = existing = cand
                else:
                    existing.semantic = max(existing.semantic, cand.semantic)
                    existing.keyword = max(existing.keyword, cand.keyword)
                existing.rrf += 1.0 / (RRF_K + rank + 1)
                existing.matched_by.append(label)
        return sorted(fused.values(), key=lambda c: -c.rrf)[:limit]

    def _corpus(self, filters: Filters) -> Optional["_Corpus"]:
        key = json.dumps(filters.as_dict(), sort_keys=True, default=str)
        corpus = self._corpora.get(key)
        if corpus is None:
            rows = self.session.execute(
                self._filtered_chunks(filters).order_by(EvidenceChunk.created_at.desc()).limit(SQLITE_SCAN_LIMIT)
            ).all()
            corpus = _Corpus.build(rows) if rows else None
            self._corpora[key] = corpus
        return corpus

    def _search_python(self, query: str, q_vec: List[float], filters: Filters):
        import numpy as np

        corpus = self._corpus(filters)
        if corpus is None:
            return [], []
        sims = corpus.matrix @ np.asarray(q_vec, dtype=float)
        keyword_scores = corpus.bm25(query)

        def take(index: int) -> Candidate:
            cand = self._candidate(*corpus.rows[index])
            cand.semantic = float(sims[index])
            cand.keyword = float(keyword_scores.get(index, 0.0))
            return cand

        # Candidates are built for the top of each list only, not the corpus.
        top_semantic = np.argsort(-sims, kind="stable")[:CANDIDATES_PER_LIST]
        top_keyword = sorted(keyword_scores, key=lambda i: (-keyword_scores[i], i))[:CANDIDATES_PER_LIST]
        built: Dict[int, Candidate] = {}
        semantic = [built.setdefault(int(i), take(int(i))) for i in top_semantic]
        keyword = [built.setdefault(i, take(i)) for i in top_keyword if keyword_scores[i] > 0]
        return semantic, keyword

    def _search_postgres(self, query: str, q_vec: List[float], filters: Filters):
        base = self._filtered_chunks(filters)
        # `<=>` is pgvector's cosine distance. Spelled as an operator because the
        # column type switches by dialect, so pgvector's comparator methods are
        # not on it; the bound vector still goes through the column's type.
        distance = EvidenceChunk.embedding.op("<=>", return_type=Float)(q_vec)
        semantic_rows = self.session.execute(
            base.add_columns(distance.label("distance")).order_by(distance).limit(CANDIDATES_PER_LIST)
        ).all()
        semantic = []
        for chunk, doc, source, dist in semantic_rows:
            cand = self._candidate(chunk, doc, source)
            cand.semantic = 1.0 - float(dist)
            semantic.append(cand)

        # Same expression as the GIN index in the migration, so it is used.
        tsv = func.to_tsvector("simple", EvidenceChunk.text)
        tsq = func.plainto_tsquery("simple", query)
        rank = func.ts_rank(tsv, tsq).label("rank")
        keyword_rows = self.session.execute(
            base.add_columns(rank).where(tsv.op("@@")(tsq)).order_by(rank.desc()).limit(CANDIDATES_PER_LIST)
        ).all()
        keyword = []
        for chunk, doc, source, score in keyword_rows:
            cand = self._candidate(chunk, doc, source)
            cand.keyword = float(score)
            keyword.append(cand)
        return semantic, keyword

    # ── Inspection ────────────────────────────────────────────

    def stats(self) -> dict:
        return {
            "documents": self.session.query(func.count(EvidenceDocument.id)).scalar() or 0,
            "chunks": self.session.query(func.count(EvidenceChunk.id)).scalar() or 0,
            "sources": self.session.query(func.count(Source.id)).scalar() or 0,
            "chunks_for_active_model": self.session.query(func.count(EvidenceChunk.id))
                .filter(EvidenceChunk.embedding_model == self.embedder.name).scalar() or 0,
            "embedding_model": self.embedder.name,
            "embedding_kind": self.embedder.kind,
            "backend": "pgvector" if self.is_postgres else "in-process (SQLite)",
        }


@dataclass
class _Corpus:
    """An in-process search index over scanned chunks (the SQLite path)."""

    rows: list
    matrix: "object"                 # numpy array, one embedding per row
    postings: Dict[str, List[tuple]]  # term -> [(row, count)]
    lengths: List[int]
    avgdl: float

    @classmethod
    def build(cls, rows) -> "_Corpus":
        import numpy as np

        postings: Dict[str, List[tuple]] = {}
        lengths = []
        for index, (chunk, _, _) in enumerate(rows):
            words = terms(chunk.text)
            lengths.append(len(words))
            for term, count in Counter(words).items():
                postings.setdefault(term, []).append((index, count))
        return cls(
            rows=rows,
            matrix=np.array([chunk.embedding for chunk, _, _ in rows], dtype=float),
            postings=postings,
            lengths=lengths,
            avgdl=(sum(lengths) / len(lengths)) or 1.0,
        )

    def bm25(self, query: str, k1: float = 1.5, b: float = 0.75) -> Dict[int, float]:
        """Okapi BM25, scored only for rows that contain a query term."""
        n = len(self.rows)
        scores: Dict[int, float] = {}
        for term in terms(query):
            hits = self.postings.get(term)
            if not hits:
                continue
            idf = math.log(1 + (n - len(hits) + 0.5) / (len(hits) + 0.5))
            for index, f in hits:
                length = self.lengths[index] or 1
                scores[index] = scores.get(index, 0.0) + idf * f * (k1 + 1) / (
                    f + k1 * (1 - b + b * length / self.avgdl))
        return scores


def iter_texts(candidates: Iterable[Candidate]) -> List[str]:
    return [c.text for c in candidates]
