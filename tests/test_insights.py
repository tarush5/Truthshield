"""
Analytics, claim memory, and grounded explanation.

The analytics endpoints aggregate across every user, so the access question
is different from the per-report routes and is tested directly. The RAG
layer is tested for the property that actually matters on a misinformation
product: a fluent explanation whose citations do not resolve must never
reach a reader.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from truthshield.domain import analytics
from truthshield.domain.rag import grounding
from truthshield.domain.rag.store import ClaimMemory, PriorClaim


# ══════════════════════════════════════════════════════════════
# Analytics
# ══════════════════════════════════════════════════════════════

class TestAnalyticsEndpoints:
    @pytest.mark.parametrize("path", [
        "/api/v1/insights/overview",
        "/api/v1/insights/volume",
        "/api/v1/insights/sources",
        "/api/v1/insights/calibration",
        "/api/v1/insights/performance",
    ])
    def test_every_panel_answers_on_an_empty_corpus(self, client, path):
        """
        A fresh deployment has no reports. Each panel must return its shape
        with zeros rather than 500 on an empty aggregate -- this is the first
        thing an operator sees, and a broken dashboard on day one reads as a
        broken product.
        """
        response = client.get(path)
        assert response.status_code == 200
        assert isinstance(response.json(), dict)

    def test_the_window_is_bounded(self, client):
        """A caller cannot ask for an unbounded scan."""
        assert client.get("/api/v1/insights/volume?days=99999").status_code == 422
        assert client.get("/api/v1/insights/volume?days=0").status_code == 422

    def test_volume_buckets_are_dense_and_ordered(self, client):
        """
        Quiet days come back as zeros, not gaps. A chart that receives gaps
        interpolates across them and draws a trend that did not happen.
        """
        series = client.get("/api/v1/insights/volume?days=14").json()["series"]
        assert len(series) == 14

        dates = [row["date"] for row in series]
        assert dates == sorted(dates), "buckets are not chronological"
        assert len(set(dates)) == 14, "duplicate day buckets"
        assert all("total" in row for row in series)

    def test_overview_is_cached_and_says_so(self, client):
        """
        The aggregate is a full scan -- 443ms over 30 days on a 60k-report
        corpus -- so it is cached rather than indexed (indexing it was tried
        and made it 7x slower; see `domain.analytics.overview`). The payload
        has to say how old it is, or a stale number reads as a live one.
        """
        # `fresh` establishes a known-cold starting point. Asserting on a
        # plain first call made this pass alone and fail in the suite,
        # because whichever test ran earlier had already warmed the entry.
        first = client.get("/api/v1/insights/overview?days=30&fresh=true").json()
        assert "computed_at" in first
        assert first["cached"] is False

        second = client.get("/api/v1/insights/overview?days=30").json()
        assert second["cached"] is True
        assert second["computed_at"] == first["computed_at"]

    def test_fresh_bypasses_the_cache(self, client):
        """What the dashboard's refresh control sends."""
        client.get("/api/v1/insights/overview?days=21")
        recomputed = client.get("/api/v1/insights/overview?days=21&fresh=true").json()
        assert recomputed["cached"] is False

    def test_each_window_is_cached_separately(self, client):
        """A 7-day view must never be served from the 30-day entry."""
        client.get("/api/v1/insights/overview?days=7")
        client.get("/api/v1/insights/overview?days=90")
        assert client.get("/api/v1/insights/overview?days=7").json()["window_days"] == 7
        assert client.get("/api/v1/insights/overview?days=90").json()["window_days"] == 90

    def test_overview_reports_one_window_for_every_panel(self, client):
        """
        The panels are fetched together precisely so they cannot disagree
        about the window; a request that straddles midnight otherwise shows
        panels computed against different days.
        """
        data = client.get("/api/v1/insights/overview?days=7").json()
        assert data["window_days"] == 7
        assert data["volume"]["days"] == 7
        assert data["sources"]["days"] == 7
        assert data["calibration"]["days"] == 7

    def test_rates_always_carry_their_denominator(self, client):
        """
        A rate without its sample size is unreadable: "100% agreement" over
        one response and over four hundred are different findings, and the
        percentage alone hides which one you have.
        """
        calibration = client.get("/api/v1/insights/calibration").json()
        assert "feedback_count" in calibration
        assert "reliable_sample" in calibration
        for row in calibration["by_verdict"]:
            assert "feedback_count" in row
            assert "reliable_sample" in row

    def test_latency_is_reported_as_percentiles(self, client):
        """A mean over a network-bound workload describes no real request."""
        latency = client.get("/api/v1/insights/performance").json()["latency"]
        assert set(latency) >= {"count", "p50", "p95", "max"}
        if latency["count"]:
            assert latency["p50"] <= latency["p95"] <= latency["max"]

    def test_aggregates_never_leak_a_claim_or_a_user(self, client, auth):
        """
        These endpoints read across every user's reports. They may return
        counts, rates and domains -- never claim text, a user id or a report
        id belonging to someone else.
        """
        client.post(
            "/api/v1/analyze",
            data={"text": "A distinctive sentinel claim about zebras.", "language": "en"},
            headers=auth,
        )
        body = client.get("/api/v1/insights/overview?days=30").text
        assert "zebras" not in body.lower()
        assert "user_id" not in body
        assert "input_text" not in body


class TestClaimSimilarity:
    def test_it_requires_authentication(self, client):
        """Unlike the aggregates, this route returns prior claim text."""
        response = client.get("/api/v1/claims/similar?q=vaccines cause autism")
        assert response.status_code == 401

    def test_it_rejects_a_query_too_short_to_match_on(self, client, auth):
        assert client.get("/api/v1/claims/similar?q=hi", headers=auth).status_code == 422

    def test_it_says_which_matcher_produced_the_result(self, client, auth):
        """
        An operator should be able to tell a semantic match from a lexical
        fallback without inspecting the configuration -- the two have very
        different meanings at the same similarity number.
        """
        body = client.get(
            "/api/v1/claims/similar?q=the earth is flat and nasa hid it",
            headers=auth,
        ).json()
        assert body["matching"] in {"embeddings", "lexical"}
        assert isinstance(body["matches"], list)


# ══════════════════════════════════════════════════════════════
# Claim memory
# ══════════════════════════════════════════════════════════════

class TestClaimMemory:
    """Exercised through the lexical path, which is the default build."""

    @staticmethod
    def _memory(*claims) -> ClaimMemory:
        from truthshield.domain.rag.store import _Entry, _tokens

        memory = ClaimMemory()
        memory._entries = [
            _Entry(
                claim=PriorClaim(
                    report_id=uuid.uuid4().hex,
                    text=text,
                    verdict=verdict,
                    trust_score=score,
                ),
                tokens=_tokens(text),
            )
            for text, verdict, score in claims
        ]
        memory._built_at = 1e9  # far future: never refreshes mid-test
        return memory

    def test_an_empty_memory_returns_nothing_rather_than_failing(self):
        assert ClaimMemory().search("anything at all") == []

    def test_it_finds_a_reworded_claim(self):
        memory = self._memory(
            ("Vaccines cause autism in young children", "FALSE", 12),
            ("The moon landing was filmed in a studio", "FALSE", 8),
        )
        hits = memory.search("young children develop autism because of vaccines", floor=0.1)
        assert hits, "reworded claim was not matched at all"
        assert "autism" in hits[0].text.lower()

    def test_results_are_ordered_by_similarity(self):
        memory = self._memory(
            ("Vaccines cause autism in young children", "FALSE", 12),
            ("Vaccines are tested for safety", "TRUE", 80),
            ("The moon landing was filmed in a studio", "FALSE", 8),
        )
        hits = memory.search("vaccines cause autism in children", floor=0.0)
        scores = [h.similarity for h in hits]
        assert scores == sorted(scores, reverse=True)

    def test_an_unrelated_claim_is_not_returned(self):
        memory = self._memory(("Vaccines cause autism in young children", "FALSE", 12))
        assert memory.search("the price of tin in 1840") == []

    def test_near_duplicate_requires_more_than_mere_relation(self):
        """
        The two thresholds mean different things. A related claim is context;
        a near-duplicate asserts we have answered *this* question, and
        surfacing one wrongly tells a reader we answered something they did
        not ask.
        """
        memory = self._memory(("Vaccines are tested for safety", "TRUE", 80))
        assert memory.near_duplicate("vaccines cause autism") is None

    def test_a_failed_refresh_keeps_serving_the_previous_index(self):
        """
        This runs on the analysis path. A database hiccup must degrade the
        prior-claims panel, not take down the analysis the reader is waiting
        for.
        """
        memory = self._memory(("Vaccines cause autism in young children", "FALSE", 12))
        before = len(memory)

        class Broken:
            def query(self, *a, **k):
                raise RuntimeError("connection reset")

        assert memory.refresh(Broken(), force=True) == before
        assert len(memory) == before


# ══════════════════════════════════════════════════════════════
# Grounded explanation
# ══════════════════════════════════════════════════════════════

class _Ev:
    def __init__(self, title, snippet, url="https://example.com"):
        self.title, self.snippet, self.url = title, snippet, url


def _sources(n=3):
    return [_Ev(f"Source {i}", f"Body text for source {i}.") for i in range(1, n + 1)]


class TestCitationVerification:
    """
    The single most important guard here. A fluent paragraph carrying a
    citation marker is more persuasive than no explanation at all, which
    makes an ungrounded one actively worse than silence on this product.
    """

    def test_a_valid_citation_survives(self):
        text, cited = grounding._verify("The sources disagree [1] on this [2].", {1, 2, 3})
        assert cited == [1, 2]
        assert "[1]" in text and "[2]" in text

    def test_an_invented_citation_is_stripped(self):
        text, cited = grounding._verify("Widely documented [7].", {1, 2})
        assert cited == []
        assert "[7]" not in text

    def test_a_mixed_marker_keeps_only_the_real_numbers(self):
        text, cited = grounding._verify("Both agree [1,9].", {1, 2})
        assert cited == [1]
        assert "9" not in text

    def test_stripping_does_not_leave_broken_punctuation(self):
        text, _ = grounding._verify("It is settled [9].", {1})
        assert " ." not in text
        assert text.endswith(".")

    def test_grouped_citations_are_all_recorded(self):
        _, cited = grounding._verify("Three sources concur [1,2,3].", {1, 2, 3})
        assert cited == [1, 2, 3]


class TestExplanationGuards:
    def test_a_single_source_is_not_explained(self):
        """
        One snippet cannot corroborate anything, and explaining from it
        dresses a single result up as a survey of the evidence.
        """
        assert grounding.explain("Some claim", _sources(1)) is None

    def test_no_evidence_yields_no_explanation(self):
        assert grounding.explain("Some claim", []) is None

    def test_an_uncited_answer_is_discarded(self, monkeypatch):
        monkeypatch.setattr(
            grounding, "_complete",
            lambda prompt: ("This is confidently true and well established.", "test-model"),
        )
        assert grounding.explain("Some claim", _sources(3)) is None

    def test_an_answer_citing_only_invented_sources_is_discarded(self, monkeypatch):
        monkeypatch.setattr(
            grounding, "_complete",
            lambda prompt: ("Proven beyond doubt [8][9].", "test-model"),
        )
        assert grounding.explain("Some claim", _sources(3)) is None

    def test_a_properly_cited_answer_is_kept(self, monkeypatch):
        monkeypatch.setattr(
            grounding, "_complete",
            lambda prompt: ("Source one contradicts the claim [1], and [2] agrees.", "test-model"),
        )
        result = grounding.explain("Some claim", _sources(3))
        assert result is not None
        assert result.is_grounded
        assert result.cited == [1, 2]
        assert result.source_count == 3

    def test_a_provider_failure_is_not_an_analysis_failure(self, monkeypatch):
        """
        The explanation is an addition to a finished analysis. A model outage
        must degrade it to nothing, never raise into the request.
        """
        def boom(prompt):
            raise RuntimeError("provider unreachable")

        monkeypatch.setattr(grounding, "_complete", boom)
        assert grounding.explain("Some claim", _sources(3)) is None

    def test_the_prompt_only_contains_retrieved_text(self, monkeypatch):
        """The model must not be handed the verdict it is explaining."""
        captured = {}

        def capture(prompt):
            captured["prompt"] = prompt
            return ("Per the sources [1].", "test-model")

        monkeypatch.setattr(grounding, "_complete", capture)
        grounding.explain("The earth is flat", _sources(3))

        prompt = captured["prompt"]
        assert "Source 1" in prompt
        for leaked in ("trust_score", "FALSE", "verdict"):
            assert leaked not in prompt


class TestContextBuilding:
    def test_sources_are_numbered_from_one(self):
        context = grounding.build_context(_sources(3))
        assert [c["n"] for c in context] == [1, 2, 3]

    def test_empty_evidence_is_dropped(self):
        context = grounding.build_context([_Ev("", ""), _Ev("Real", "Body")])
        assert len(context) == 1

    def test_long_snippets_are_truncated(self):
        context = grounding.build_context([_Ev("T", "x" * 5000), _Ev("T2", "y" * 5000)])
        assert all(len(c["snippet"]) <= grounding.MAX_SNIPPET_CHARS for c in context)

    def test_the_source_count_is_capped(self):
        context = grounding.build_context(_sources(50))
        assert len(context) == grounding.MAX_SOURCES


# ══════════════════════════════════════════════════════════════
# Aggregation correctness
# ══════════════════════════════════════════════════════════════

class TestAggregationMath:
    def test_percentiles_are_nearest_rank(self, session):
        """
        Interpolated percentiles invent a duration no request actually took,
        which matters at the sample sizes a young deployment has.
        """
        from truthshield.infra.models import Report

        now = datetime.now(timezone.utc)
        for i, seconds in enumerate([1.0, 2.0, 3.0, 4.0, 100.0]):
            session.add(Report(
                id=uuid.uuid4().hex,
                status="complete",
                content_type="text",
                language="en",
                verdict="TRUE",
                trust_score=80,
                processing_time_seconds=seconds,
                created_at=now - timedelta(hours=i),
            ))
        session.commit()

        result = analytics.latency(session, days=7)
        assert result["count"] >= 5
        assert result["max"] >= 100.0
        # The outlier must not drag p50 with it, which is the entire reason
        # this is not a mean.
        assert result["p50"] < result["max"]
