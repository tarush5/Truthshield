"""Citation integrity checks, unit and through the evidence engine."""

from datetime import datetime, timedelta, timezone

from truthshield.investigations import citations
from truthshield.investigations.engines.evidence import EvidenceEngine

CHUNK = ("The municipal corporation said on Monday that the Ganga bridge reopened to traffic.\n"
         "Repairs took three weeks. Heavy vehicles remain restricted until further notice.")


def source(**over):
    base = {"url": "https://www.example-news.in/bridge", "publisher": "example-news.in",
            "passage": "Repairs took three weeks.", "published_at": None}
    return {**base, **over}


class TestCheck:
    def test_faithful_citation_is_verified(self):
        c = citations.check(source(), passage_found=True)
        assert c["status"] == "verified" and c["problems"] == []

    def test_passage_matching_ignores_whitespace_and_case(self):
        assert citations.passage_in("said on monday that   the GANGA bridge", CHUNK)
        assert not citations.passage_in("the bridge collapsed", CHUNK)
        assert not citations.passage_in("", CHUNK)

    def test_missing_passage_is_a_mismatch(self):
        c = citations.check(source(), passage_found=False)
        assert c["status"] == "mismatch" and "not found" in c["problems"][0]

    def test_publisher_must_be_the_linked_site(self):
        assert citations.check(source(publisher="news.example-news.in"), passage_found=True)["status"] == "verified"
        bad = citations.check(source(publisher="reuters.com"), passage_found=True)
        assert bad["status"] == "mismatch" and bad["publisher_matches_url"] is False

    def test_invalid_urls_are_rejected(self):
        for url in ("javascript:alert(1)", "https://user:pw@example-news.in/x", "not a url"):
            assert citations.check(source(url=url), passage_found=True)["url_valid"] is False

    def test_future_publication_date_is_not_relied_on(self):
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        c = citations.check(source(published_at=future), passage_found=True)
        assert c["status"] == "mismatch" and c["published_date"] == "in_future"

    def test_unstored_source_is_unverified_not_verified(self):
        assert citations.check(source(), passage_found=None)["status"] == "unverified"

    def test_truncation_is_flagged(self):
        assert citations.check(source(passage="x" * 500), passage_found=True)["passage_truncated"]


def _run_with(monkeypatch, snippet, chunk_text, verdict_name="FALSE"):
    from truthshield.domain.types import Claim, ClaimVerdict, EvidenceItem, Stance, Verdict
    from truthshield.rag.engine import Retrieval
    from truthshield.settings import get_settings
    from tests.test_v2_engines import ctx

    monkeypatch.setattr(get_settings(), "OFFLINE_MODE", False)
    url = "https://www.who.int/news/x"

    async def fake_verify(self, claims):
        retrieval = Retrieval(claim=claims[0]["text"], variants=[], embedding={}, reranker="none", filters={})
        retrieval.passages = [{"url": url, "chunk_id": "c1", "document_id": "d1", "category": "OFFICIAL",
                               "retrieved_at": None, "published_at": None, "content_scope": None, "scores": None}]
        retrieval.chunk_texts = {"c1": chunk_text}
        return [(ClaimVerdict(
            claim=Claim(text=claims[0]["text"]), verdict=Verdict[verdict_name], confidence=0.8,
            reasoning="Refuted.", evidence=[EvidenceItem(title="WHO", url=url, snippet=snippet,
                                                         source_score=0.95, stance=Stance.REFUTES)],
        ), retrieval)]

    monkeypatch.setattr(EvidenceEngine, "_verify", fake_verify)
    c = ctx("Drinking bleach cures COVID.")
    c.artifacts["claims"] = [{"id": "C1", "text": "Drinking bleach cures COVID."}]
    return EvidenceEngine().run(c)


class TestEngine:
    def test_faithful_citation_decides_the_claim(self, monkeypatch):
        result = _run_with(monkeypatch, "Bleach does not cure COVID.",
                           "Myth busters. Bleach does not cure COVID. Do not drink it.")
        claim = result.artifacts["claims"][0]
        assert claim["assessment"] == "CONTRADICTED"
        assert claim["sources"][0]["citation"]["status"] == "verified"
        assert claim["citations"] == {"verified": 1, "unverified": 0, "mismatch": 0}

    def test_a_passage_absent_from_the_stored_source_cannot_decide(self, monkeypatch):
        result = _run_with(monkeypatch, "Bleach does not cure COVID.",
                           "This page is about hand-washing technique.")
        claim = result.artifacts["claims"][0]
        assert claim["assessment"] == "INSUFFICIENT_EVIDENCE" and claim["downgraded"]
        assert "citation check" in claim["reasoning"]
        assert claim["sources"][0]["citation"]["status"] == "mismatch"
        assert result.signals == [], "a rejected citation never becomes a risk signal"


def test_end_to_end_citations_are_checked_against_the_stored_chunk(client, auth):
    """Real store, real retrieval, real adjudicator: every cited passage is found in its chunk."""
    import uuid

    from tests.test_v2_evidence_api import account, ingest

    marker = f"z{uuid.uuid4().hex[:8]}"
    analyst = account(client, role="ANALYST")
    assert ingest(client, analyst, marker).status_code == 201
    claim = f"The {marker} health advisory says lemon water cures cancer."
    r = client.post("/api/v1/investigations", json={"type": "text", "content": claim}, headers=auth)
    inv = client.get(f"/api/v1/investigations/{r.json()['id']}", headers=auth).json()
    checked = [c for c in inv["result"]["claims"] if c.get("sources")]
    assert checked, "the ingested advisory should have been retrieved"
    for c in checked:
        for s in c["sources"]:
            assert s["attribution"] == "evidence_store"
            assert s["citation"]["status"] == "verified", s["citation"]
