"""
Evidence store, source registry and claim search endpoints (2.0 Phase 2).
"""

import uuid
from datetime import datetime, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from truthshield.api.deps import require_principal, require_role
from truthshield.api.errors import ApiError
from truthshield.infra.database import get_session
from truthshield.infra.models import ClaimRecord, EvidenceDocument, Investigation, Source
from truthshield.investigations.service import iso
from truthshield.services.audit import record as record_audit
from truthshield.services.auth import Principal

evidence_router = APIRouter(prefix="/evidence", tags=["evidence"])
sources_router = APIRouter(prefix="/sources", tags=["sources"])
claims_v2_router = APIRouter(prefix="/claims", tags=["claims"])

CATEGORIES = ("PRIMARY", "OFFICIAL", "SECONDARY", "COMMUNITY", "UNKNOWN")


def _store(session: Session):
    from truthshield.providers import get_embedding_model
    from truthshield.rag import EvidenceStore
    return EvidenceStore(session, get_embedding_model())


# ── Search ────────────────────────────────────────────────────

@evidence_router.get("/search")
def search(
    q: str = Query(..., min_length=2, max_length=500),
    category: List[str] = Query(default=[]),
    min_credibility: Optional[float] = Query(None, ge=0, le=1),
    exclude_domain: List[str] = Query(default=[]),
    limit: int = Query(10, ge=1, le=50),
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
):
    """
    Hybrid search of the evidence store: semantic (embeddings) and keyword,
    fused with Reciprocal Rank Fusion, then reranked. Every score is returned.
    """
    from truthshield.rag import Filters
    from truthshield.rag.rerank import get_reranker
    from truthshield.rag.text import best_passage

    bad = [c for c in category if c not in CATEGORIES]
    if bad:
        raise ApiError(400, "BAD_REQUEST", f"Unknown category: {', '.join(bad)}")
    store = _store(session)
    filters = Filters(categories=category or None, min_credibility=min_credibility,
                      exclude_domains=exclude_domain or None)
    candidates = store.search(q, filters=filters, limit=max(limit * 3, 20))
    reranker = get_reranker()
    ranked = reranker.rerank(q, candidates)[:limit]
    return {
        "query": q,
        "embedding": {"model": store.embedder.name, "kind": store.embedder.kind},
        "reranker": {"name": reranker.name, "learned": reranker.learned},
        "filters": filters.as_dict(),
        "results": [
            {
                "chunk_id": r["candidate"].chunk_id,
                "document_id": r["candidate"].document_id,
                "title": r["candidate"].title,
                "url": r["candidate"].url,
                "publisher": r["candidate"].publisher,
                "category": r["candidate"].category,
                "credibility": round(r["candidate"].credibility, 2),
                "content_scope": r["candidate"].content_scope,
                "published_at": iso(r["candidate"].published_at),
                "retrieved_at": iso(r["candidate"].retrieved_at),
                "passage": best_passage(q, r["candidate"].text),
                "scores": {"final": r["score"], "components": r["components"],
                           "semantic": round(r["candidate"].semantic, 3),
                           "keyword": round(r["candidate"].keyword, 3),
                           "matched_by": sorted(set(r["candidate"].matched_by))},
            }
            for r in ranked
        ],
    }


@evidence_router.get("/stats")
def stats(principal: Principal = Depends(require_principal), session: Session = Depends(get_session)):
    from truthshield.rag.rerank import get_reranker
    return {**_store(session).stats(), "reranker": get_reranker().name}


@evidence_router.get("/{document_id}")
def document(document_id: uuid.UUID, principal: Principal = Depends(require_principal),
             session: Session = Depends(get_session)):
    """One stored document with its chunks (embeddings omitted)."""
    doc = session.get(EvidenceDocument, document_id)
    if doc is None:
        raise ApiError(404, "NOT_FOUND", "Evidence document not found.")
    return {
        "id": str(doc.id),
        "url": doc.url,
        "title": doc.title,
        "author": doc.author,
        "published_at": iso(doc.published_at),
        "retrieved_at": iso(doc.retrieved_at),
        "content_scope": doc.content_scope,
        "content_sha256": doc.content_sha256,
        "provider": doc.provider,
        "source": _source_out(doc.source) if doc.source else None,
        "chunks": [{"id": str(c.id), "index": c.chunk_index, "text": c.text,
                    "embedding_model": c.embedding_model} for c in doc.chunks],
    }


# ── Ingestion (analysts) ──────────────────────────────────────

class IngestRequest(BaseModel):
    url: Optional[str] = Field(None, max_length=2048, description="Fetch and ingest a public page.")
    title: Optional[str] = Field(None, max_length=500)
    text: Optional[str] = Field(None, max_length=200_000, description="Or ingest supplied text.")
    source_url: Optional[str] = Field(None, max_length=2048, description="Where the supplied text came from.")
    published_at: Optional[datetime] = None

    @model_validator(mode="after")
    def _one_source(self):
        if bool(self.url) == bool(self.text):
            raise ValueError("Provide either url (to fetch) or text with source_url.")
        if self.text and not self.source_url:
            raise ValueError("source_url is required with text, so the evidence stays citable.")
        return self


def fetch_article(url: str) -> dict:
    """Fetch a public page through the SSRF guard and keep its readable text."""
    from bs4 import BeautifulSoup

    from truthshield.security.url_guard import safe_get

    response = safe_get(url, headers={"User-Agent": "TruthShield-Evidence/2.0"}, timeout=(4.0, 10.0),
                        max_bytes=3 * 1024 * 1024)
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "form", "iframe"]):
        tag.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    text = "\n".join(p.get_text(" ", strip=True) for p in main.find_all(["p", "li", "h1", "h2", "h3", "blockquote"]))
    if len(text) < 200:
        text = main.get_text(" ", strip=True)
    published = None
    meta = soup.find("meta", attrs={"property": "article:published_time"}) or soup.find("time", attrs={"datetime": True})
    raw = (meta.get("content") or meta.get("datetime")) if meta else None
    if raw:
        try:
            published = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            published = None
    title = soup.title.string.strip() if soup.title and soup.title.string else url
    return {"title": title[:500], "text": text[:200_000], "published_at": published}


@evidence_router.post("/documents", status_code=201)
def ingest(
    body: IngestRequest,
    principal: Principal = Depends(require_role("ANALYST", "ADMIN")),
    session: Session = Depends(get_session),
):
    """Add a trusted document to the evidence store (analysts and admins)."""
    from truthshield.security.url_guard import BlockedURLError

    if body.url:
        try:
            page = fetch_article(body.url)
        except BlockedURLError as exc:
            raise ApiError(400, "BLOCKED_URL", str(exc))
        except Exception as exc:
            raise ApiError(502, "UPSTREAM_FAILED", f"The page could not be fetched ({type(exc).__name__}).")
        url, title, text, scope = body.url, body.title or page["title"], page["text"], "full_text"
        published = body.published_at or page["published_at"]
    else:
        url, title, text, scope, published = body.source_url, body.title or body.source_url, body.text, "uploaded", body.published_at
    if len((text or "").strip()) < 40:
        raise ApiError(422, "VALIDATION_ERROR", "Too little readable text to ingest.")

    store = _store(session)
    doc, created = store.ingest(url=url, title=title, content=text, provider="analyst", content_scope=scope,
                                credibility_prior=0.6, published_at=published, ingested_by=principal.user_id)
    record_audit(session, principal, "evidence.ingest", f"evidence:{doc.id}",
                 {"url": doc.url, "created": created, "chunks": len(doc.chunks)})
    return {"id": str(doc.id), "created": created, "chunks": len(doc.chunks), "url": doc.url,
            "source": _source_out(doc.source) if doc.source else None}


# ── Source registry ───────────────────────────────────────────

def _source_out(s: Source) -> dict:
    return {"id": str(s.id), "domain": s.domain, "name": s.name, "category": s.category,
            "credibility": s.credibility, "curated": s.curated, "notes": s.notes,
            "first_seen_at": iso(s.first_seen_at), "last_seen_at": iso(s.last_seen_at),
            "documents": len(s.documents)}


@sources_router.get("")
def list_sources(
    q: str = Query("", max_length=200),
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
):
    query = session.query(Source)
    if q:
        query = query.filter(Source.domain.ilike(f"%{q.strip().lower()}%"))
    if category:
        query = query.filter(Source.category == category.upper())
    total = query.count()
    rows = query.order_by(Source.last_seen_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [_source_out(s) for s in rows], "total": total, "page": page, "page_size": page_size,
            "categories": list(CATEGORIES)}


class SourceUpdate(BaseModel):
    category: Optional[Literal["PRIMARY", "OFFICIAL", "SECONDARY", "COMMUNITY", "UNKNOWN"]] = None
    credibility: Optional[float] = Field(None, ge=0, le=1)
    notes: Optional[str] = Field(None, max_length=2000)


@sources_router.patch("/{source_id}")
def update_source(source_id: uuid.UUID, body: SourceUpdate,
                  principal: Principal = Depends(require_role("ADMIN")),
                  session: Session = Depends(get_session)):
    """Curate a source. A curated source keeps its rating against later heuristics."""
    source = session.get(Source, source_id)
    if source is None:
        raise ApiError(404, "NOT_FOUND", "Source not found.")
    changes = {}
    for field in ("category", "credibility", "notes"):
        value = getattr(body, field)
        if value is not None and value != getattr(source, field):
            changes[field] = {"from": getattr(source, field), "to": value}
            setattr(source, field, value)
    source.curated = True
    session.commit()
    if changes:
        record_audit(session, principal, "source.update", f"source:{source.domain}", changes)
    return _source_out(source)


# ── Claims ────────────────────────────────────────────────────

@claims_v2_router.get("")
def search_claims(
    q: str = Query("", max_length=200),
    assessment: Optional[str] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
):
    """Claims from the caller's investigations (all, for admins), newest first."""
    query = session.query(ClaimRecord, Investigation).join(Investigation, ClaimRecord.investigation_id == Investigation.id)
    if principal.role != "ADMIN":
        query = query.filter(Investigation.user_id == principal.user_id)
    if q:
        query = query.filter(ClaimRecord.text.ilike(f"%{q.strip()}%"))
    if assessment:
        query = query.filter(ClaimRecord.assessment == assessment.upper())
    rows = query.order_by(ClaimRecord.created_at.desc()).limit(limit).all()
    return {"items": [
        {"claim_key": c.claim_key, "text": c.text, "assessment": c.assessment, "confidence": c.confidence,
         "source_count": c.source_count, "investigation_id": str(i.id), "public_id": i.public_id,
         "created_at": iso(c.created_at)}
        for c, i in rows
    ], "generated_at": datetime.now(timezone.utc).isoformat()}
