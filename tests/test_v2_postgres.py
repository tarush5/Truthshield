"""
The pgvector and full-text paths of the evidence store, against real Postgres.

Skipped unless TEST_POSTGRES_URL points at a migrated database with the
`vector` extension -- CI provides one (pgvector/pgvector:pg16). The rest of the
suite runs on SQLite, where the store scores vectors in Python instead.
"""

import os
import uuid

import pytest

PG_URL = os.environ.get("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not PG_URL, reason="TEST_POSTGRES_URL not set (CI provides a pgvector database)")


@pytest.fixture
def pg_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(PG_URL)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def test_vector_extension_and_indexes_exist(pg_session):
    from sqlalchemy import text

    assert pg_session.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'")).scalar() == "vector"
    indexes = {r[0] for r in pg_session.execute(text(
        "SELECT indexname FROM pg_indexes WHERE tablename = 'evidence_chunks'"))}
    assert {"ix_evidence_chunks_embedding_hnsw", "ix_evidence_chunks_fts"} <= indexes


def test_hybrid_search_on_pgvector(pg_session):
    from truthshield.infra.models import EvidenceDocument
    from truthshield.providers.embeddings import HashingEmbedding
    from truthshield.rag import EvidenceStore, Filters

    store = EvidenceStore(pg_session, HashingEmbedding())
    assert store.is_postgres
    marker = f"pgv{uuid.uuid4().hex[:8]}"
    docs = []
    try:
        docs.append(store.ingest(url=f"https://who.int/{marker}", title="WHO",
                                 content=f"The {marker} outbreak was declared over by health authorities.",
                                 provider="test", credibility_prior=0.95)[0])
        docs.append(store.ingest(url=f"https://blog.example/{marker}", title="Blog",
                                 content="Summer salad recipes and cold soups.", provider="test",
                                 credibility_prior=0.3)[0])

        results = store.search(f"{marker} outbreak declared over")
        assert results and marker in results[0].text
        assert "semantic" in results[0].matched_by and "keyword" in results[0].matched_by
        assert -1.0 <= results[0].semantic <= 1.0

        official = store.search(f"{marker} outbreak", filters=Filters(categories=["OFFICIAL"]))
        assert official and all(c.category == "OFFICIAL" for c in official)
    finally:
        for doc in docs:
            pg_session.delete(pg_session.get(EvidenceDocument, doc.id))
        pg_session.commit()
