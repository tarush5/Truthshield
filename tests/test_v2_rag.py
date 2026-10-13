"""
Evidence store, hybrid retrieval, reranking, the RAG engine, and providers.

Runs on SQLite with the lexical hashing embedder, which is what CI and a bare
install have. The pgvector path is exercised in CI against real Postgres
(tests/test_v2_postgres.py).
"""

import asyncio
import uuid

import pytest

from truthshield.providers.base import BaseSearchProvider, SearchHit
from truthshield.providers.embeddings import HashingEmbedding
from truthshield.rag import EvidenceStore, Filters, RAGEngine
from truthshield.rag.rerank import FeatureReranker
from truthshield.rag.text import best_passage, bm25_scores, chunk_text, expand_query


def unique(word="topic"):
    return f"{word}{uuid.uuid4().hex[:8]}"


@pytest.fixture
def store(session):
    return EvidenceStore(session, HashingEmbedding())


class FakeSearch(BaseSearchProvider):
    name = "fake"

    def __init__(self, hits=None, fail=False):
        self.hits, self.fail, self.calls = hits or [], fail, 0

    @property
    def available(self):
        return True

    async def search(self, query, *, limit=12):
        self.calls += 1
        if self.fail:
            raise ConnectionError("provider down")
        return self.hits


# ── Text utilities ────────────────────────────────────────────

class TestText:
    def test_chunks_respect_sentences_and_overlap(self):
        text = " ".join(f"Sentence number {i} talks about subject {i}." for i in range(40))
        chunks = chunk_text(text, target=200)
        assert len(chunks) > 3
        assert all(c.text.endswith(".") for c in chunks)
        assert chunks[1].text.split(".")[0] in chunks[0].text, "consecutive chunks overlap by a sentence"
        assert all(text[c.start:c.end] == c.text for c in chunks)

    def test_query_expansion_strategies(self):
        variants = dict(expand_query("The WHO did not approve Covaxin in March 2021"))
        assert variants["original"].startswith("The WHO")
        assert "not" not in variants["neutral"].split()
        assert "covaxin" in variants["keywords"] and "the" not in variants["keywords"].split()
        assert "WHO" in variants["entities"] and "2021" in variants["entities"]

    def test_bm25_prefers_matching_documents(self):
        scores = bm25_scores("lemon water cancer", ["lemon water does not cure cancer", "stock markets rose today"])
        assert scores[0] > 0 and scores[1] == 0

    def test_best_passage_picks_relevant_sentences(self):
        text = "Weather was mild. Lemon water does not cure cancer, oncologists say. Markets were flat. Rain is due."
        assert "Lemon water" in best_passage("lemon water cures cancer", text, sentences=1)


# ── Embeddings ───────────────────────────────────────────────

class TestEmbeddings:
    def test_hashing_embedding_is_deterministic_normalised_and_lexical(self):
        model = HashingEmbedding()
        a, b = model.embed(["vaccines cause autism", "vaccines cause autism"])
        assert a == b and abs(sum(x * x for x in a) - 1.0) < 1e-9 and len(a) == 384
        assert model.kind == "lexical"

    def test_overlap_scores_higher_than_unrelated(self):
        model = HashingEmbedding()
        q, near, far = model.embed(["lemon water cures cancer", "does lemon water cure cancer", "football results"])
        dot = lambda x, y: sum(i * j for i, j in zip(x, y))
        assert dot(q, near) > dot(q, far)


# ── Store ────────────────────────────────────────────────────

class TestStore:
    def test_ingest_is_idempotent_per_url_and_content(self, store):
        url = f"https://www.example-news.org/{unique()}"
        doc, created = store.ingest(url=url, title="Title", content="Body text about things.", provider="test")
        again, created_again = store.ingest(url=url + "/", title="Title", content="Body text about things.", provider="test")
        assert created and not created_again and again.id == doc.id
        assert doc.source.domain == "example-news.org"

    def test_changed_content_replaces_chunks(self, store):
        url = f"https://example-news.org/{unique()}"
        store.ingest(url=url, title="T", content="First version of the article.", provider="test")
        doc, _ = store.ingest(url=url, title="T", content="Second version, rewritten entirely.", provider="test")
        assert all("Second version" in c.text for c in doc.chunks)

    def test_hybrid_search_finds_by_meaning_and_keyword(self, store):
        marker = unique("zylophant")
        store.ingest(url=f"https://who.int/{marker}", title="WHO statement",
                     content=f"The {marker} outbreak has been declared over by health authorities.",
                     provider="test", credibility_prior=0.95)
        store.ingest(url=f"https://blog.example/{marker}", title="Unrelated",
                     content="Recipes for summer salads and cold soups.", provider="test")
        results = store.search(f"{marker} outbreak declared over")
        assert results and marker in results[0].text
        assert "keyword" in results[0].matched_by and "semantic" in results[0].matched_by

    def test_filters_apply(self, store):
        marker = unique("quorvex")
        store.ingest(url=f"https://pib.gov.in/{marker}", title="Official", content=f"{marker} scheme details.",
                     provider="test", credibility_prior=0.95)
        store.ingest(url=f"https://random-blog.xyz/{marker}", title="Blog", content=f"{marker} scheme rumours.",
                     provider="test", credibility_prior=0.2)
        official = store.search(f"{marker} scheme", filters=Filters(categories=["OFFICIAL"]))
        assert official and all(c.category == "OFFICIAL" for c in official)
        excluded = store.search(f"{marker} scheme", filters=Filters(exclude_domains=["random-blog.xyz"]))
        assert all(c.publisher != "random-blog.xyz" for c in excluded)

    def test_vectors_from_another_model_are_never_compared(self, store, session):
        from truthshield.infra.models import EvidenceChunk

        marker = unique("crossmodel")
        doc, _ = store.ingest(url=f"https://x.org/{marker}", title="T", content=f"{marker} content.", provider="test")
        for chunk in doc.chunks:
            chunk.embedding_model = "some-other-model"
        session.commit()
        assert not [c for c in store.search(marker) if marker in c.text]
        assert session.query(EvidenceChunk).filter(EvidenceChunk.document_id == doc.id).count() > 0

    def test_curated_sources_keep_their_rating(self, store, session):
        domain = f"{unique('curated')}.org"
        source = store.upsert_source(domain, credibility_prior=0.9)
        source.curated, source.credibility, source.category = True, 0.3, "COMMUNITY"
        session.commit()
        store.upsert_source(domain, credibility_prior=0.99)
        assert source.credibility == 0.3 and source.category == "COMMUNITY"


# ── Reranking ────────────────────────────────────────────────

class TestCorpusIndex:
    def test_indexed_bm25_matches_the_reference_implementation(self):
        from types import SimpleNamespace

        from truthshield.rag.store import _Corpus

        texts = ["Lemon water does not cure cancer, doctors say.",
                 "Stock markets rose today as banks gained.",
                 "Cancer researchers found no effect of lemon water on tumours. Lemon lemon.",
                 ""]
        rows = [(SimpleNamespace(text=t, embedding=[0.0, 1.0]), None, None) for t in texts]
        corpus = _Corpus.build(rows)
        for query in ("lemon water cancer", "banks banks", "nothing matches here"):
            reference = bm25_scores(query, texts)
            indexed = corpus.bm25(query)
            assert [round(indexed.get(i, 0.0), 9) for i in range(len(texts))] == [round(x, 9) for x in reference]

    def test_corpus_is_reused_across_searches_and_dropped_on_ingest(self, store):
        # Invented words only: this store is shared with tests that expect
        # ordinary claims to find nothing.
        a, b, c = unique("orvane"), unique("plessit"), unique("quorrad")
        store.ingest(url=f"https://example.org/{a}", title=a, content=f"{a} {b} returns.", provider="test")
        store.search(f"{a} {b}")
        cached = dict(store._corpora)
        store.search(f"{a}")
        assert store._corpora == cached and cached, "second search should reuse the scanned corpus"
        store.ingest(url=f"https://example.org/{a}-2", title=a, content=f"{a} {c} again.", provider="test")
        assert not store._corpora
        assert any(c in cand.text for cand in store.search(f"{a} {c}"))


class TestRerank:
    def test_components_are_exposed_and_credibility_matters(self, store):
        from truthshield.rag.store import Candidate

        a = Candidate("1", "d", "t", "", "", "a.org", "SECONDARY", 0.9, None, None, "snippet", semantic=0.5, keyword=1.0)
        b = Candidate("2", "d", "t", "", "", "b.org", "UNKNOWN", 0.2, None, None, "snippet", semantic=0.5, keyword=1.0)
        ranked = FeatureReranker().rerank("q", [b, a])
        assert ranked[0]["candidate"].chunk_id == "1"
        assert set(ranked[0]["components"]) == {"relevance", "keyword", "credibility", "recency"}


# ── RAG engine ───────────────────────────────────────────────

class TestRAGEngine:
    def run(self, engine, claim):
        return asyncio.run(engine.retrieve(claim))

    def test_uses_the_store_without_live_search_when_it_has_enough(self, session):
        marker = unique("plindor")
        store = EvidenceStore(session, HashingEmbedding())
        for i in range(3):
            store.ingest(url=f"https://news{i}.org/{marker}", title=f"{marker} report {i}",
                         content=f"The {marker} bridge collapsed on Monday, officials confirmed.", provider="test")
        search = FakeSearch()
        engine = RAGEngine(session, embedder=HashingEmbedding(), search=search, min_local_hits=2)
        retrieval = self.run(engine, f"The {marker} bridge collapsed on Monday")
        assert search.calls == 0 and retrieval.live_search == "not_needed"
        assert retrieval.passages and retrieval.passages[0]["document_id"]
        assert retrieval.passages[0]["scores"]["components"]

    def test_falls_back_to_live_search_and_ingests_results(self, session):
        marker = unique("vantrel")
        hits = [SearchHit(title=f"{marker} dam opened", url=f"https://reuters.com/{marker}",
                          snippet=f"The {marker} dam was opened by the minister on Friday.",
                          publisher="reuters.com", credibility=0.9, provider="fake")]
        search = FakeSearch(hits)
        engine = RAGEngine(session, embedder=HashingEmbedding(), search=search, min_local_hits=3)
        retrieval = self.run(engine, f"The {marker} dam was opened on Friday")
        assert search.calls == 1 and retrieval.live_search == "used" and retrieval.ingested == 1
        assert retrieval.passages[0]["publisher"] == "reuters.com"

        # A second identical question is answered from the store.
        again = self.run(RAGEngine(session, embedder=HashingEmbedding(), search=search, min_local_hits=1),
                         f"The {marker} dam was opened on Friday")
        assert search.calls == 1 and again.passages

    def test_provider_failure_is_reported_not_papered_over(self, session):
        engine = RAGEngine(session, embedder=HashingEmbedding(), search=FakeSearch(fail=True), min_local_hits=3)
        retrieval = self.run(engine, f"{unique('nothing')} happened somewhere unusual")
        assert retrieval.live_search == "failed"
        assert "Evidence unavailable from the search provider" in retrieval.live_detail
        # Whatever the store already held may still be returned; nothing new
        # was invented or ingested on the failed provider's behalf.
        assert retrieval.ingested == 0 and retrieval.live_hits == 0

    def test_live_searches_for_several_claims_run_concurrently(self, session):
        class SlowSearch(FakeSearch):
            async def search(self, query, *, limit=12):
                self.calls += 1
                await asyncio.sleep(0.4)
                marker = query.split()[1]
                return [SearchHit(title=f"{marker} report", url=f"https://apnews.com/{marker}",
                                  snippet=f"{query}, officials said.", publisher="apnews.com",
                                  credibility=0.9, provider="slow")]

        import time

        claims = [f"The {unique('kestrel')} canal reopened after repairs on Tuesday" for _ in range(3)]
        search = SlowSearch()
        # Force the live path whatever earlier tests left in the shared store.
        engine = RAGEngine(session, embedder=HashingEmbedding(), search=search, min_local_hits=10_000)
        started = time.perf_counter()
        retrievals = asyncio.run(engine.retrieve_many(claims))
        elapsed = time.perf_counter() - started

        assert search.calls == 3
        assert elapsed < 1.0, f"three 0.4 s searches took {elapsed:.2f} s; they ran one after another"
        # Each claim keeps its own results, in order.
        for claim, retrieval in zip(claims, retrievals):
            assert retrieval.claim == claim and retrieval.live_search == "used"
            assert claim.split()[1] in retrieval.passages[0]["url"]

    def test_one_failed_search_does_not_sink_the_others(self, session):
        class Flaky(FakeSearch):
            async def search(self, query, *, limit=12):
                self.calls += 1
                if "broken" in query:
                    raise TimeoutError("slow provider")
                return [SearchHit(title=query, url=f"https://bbc.co.uk/{uuid.uuid4().hex}", snippet=query,
                                  publisher="bbc.co.uk", credibility=0.85, provider="flaky")]

        good = f"The {unique('harbour')} ferry service resumed on Monday morning"
        bad = f"The broken {unique('pier')} story spread quickly online"
        engine = RAGEngine(session, embedder=HashingEmbedding(), search=Flaky(), min_local_hits=10_000)
        ok, failed = asyncio.run(engine.retrieve_many([good, bad]))
        assert ok.live_search == "used" and ok.passages
        assert failed.live_search == "failed" and failed.ingested == 0


# ── Providers ────────────────────────────────────────────────

class TestProviders:
    def test_offline_resolves_every_network_provider_to_unavailable(self):
        from truthshield import providers

        providers.reset_all()
        status = providers.status()
        assert status["llm"]["available"] is False and status["llm"]["detail"]
        assert status["search"]["available"] is False
        assert status["embeddings"]["kind"] in ("lexical", "semantic")

    def test_circuit_breaker_opens_and_fails_fast(self):
        from truthshield.providers.resilience import CircuitOpenError, call_with_retry

        name = unique("svc")
        calls = []

        def broken():
            calls.append(1)
            raise ConnectionError("down")

        for _ in range(3):
            with pytest.raises(ConnectionError):
                call_with_retry(broken, name=name, attempts=2, sleep=lambda s: None)
        with pytest.raises(CircuitOpenError):
            call_with_retry(broken, name=name, attempts=2, sleep=lambda s: None)
        assert len(calls) == 5, "the open breaker stopped further calls"

    def test_anthropic_refusal_is_not_treated_as_text(self, monkeypatch):
        from types import SimpleNamespace

        from truthshield.providers.llm import AnthropicProvider

        response = SimpleNamespace(stop_reason="refusal", content=[], model="claude-opus-5-5",
                                   usage=SimpleNamespace(input_tokens=10, output_tokens=0))
        provider = AnthropicProvider("key")
        fake_client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: response)))
        monkeypatch.setattr(provider, "_get_client", lambda: fake_client)
        result = provider.complete(system="s", prompt="p")
        assert result.refused and result.text is None and not result.ok

    def test_anthropic_request_shape(self, monkeypatch):
        from types import SimpleNamespace

        from truthshield.providers.llm import AnthropicProvider

        seen = {}

        def create(**kwargs):
            seen.update(kwargs)
            return SimpleNamespace(stop_reason="end_turn", model=kwargs["model"],
                                   content=[SimpleNamespace(type="text", text="Grounded answer [S1].")],
                                   usage=SimpleNamespace(input_tokens=120, output_tokens=30))

        provider = AnthropicProvider("key")
        monkeypatch.setattr(provider, "_get_client",
                            lambda: SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create))))
        result = provider.complete(system="sys", prompt="prompt")
        assert result.ok and result.input_tokens == 120 and result.output_tokens == 30
        assert seen["model"] == "claude-opus-5-5"
        assert seen["fallbacks"] == "default" and seen["betas"] == ["server-side-fallback-2026-07-01"]
        assert "temperature" not in seen and "thinking" not in seen
