"""
Query focus, fraud signals, and provider visibility.

The first two are the substance of what the retrieval path gets wrong and
what the text path can add; the third exists because a silently degraded
deployment is indistinguishable from a healthy one without it.
"""

import pytest

from truthshield.detectors.fraud import FLAG_THRESHOLD, score_text
from truthshield.domain.verdict.focus import entity_query, focus_terms


# ══════════════════════════════════════════════════════════════
# Query focus
# ══════════════════════════════════════════════════════════════

class TestSentenceInitialCapitals:
    """
    The bug this module exists to fix.

    The previous extractor matched capitalised words as entities, which
    matches the first word of any English sentence. Every case below was
    measured against the real implementation and sent the wrong query.
    """

    @pytest.mark.parametrize("claim,must_include,must_not_be", [
        ("Drinking bleach cures COVID-19 within 24 hours.", "bleach", "drinking"),
        ("Humans only use ten percent of their brains.", "brains", "humans"),
        ("Vaccines cause autism according to a 2019 WHO study.", "autism", "vaccines"),
        ("Smoking tobacco causes lung cancer.", "tobacco", "smoking"),
    ])
    def test_the_query_is_about_the_subject_not_the_first_word(
        self, claim, must_include, must_not_be,
    ):
        query = entity_query(claim).lower()
        assert must_include in query, f"{claim!r} -> {query!r} lost its subject"
        assert query != must_not_be, "query collapsed to the sentence-initial word"

    def test_a_real_proper_noun_survives(self):
        """The fix must not throw out actual names along with the grammar."""
        assert "nasa" in entity_query("The Earth is flat and NASA has been hiding it.").lower()

    def test_a_sentence_initial_name_repeated_elsewhere_is_kept(self):
        """
        A capital that opens a sentence *and* appears capitalised again is a
        name, not grammar, and must survive.
        """
        terms = " ".join(focus_terms("Paris is lovely. Many visit Paris each spring.")).lower()
        assert "paris" in terms


class TestAcronyms:
    """
    The old regex was `[A-Z][a-z]+`, which requires a lowercase tail and so
    could not match an acronym at all -- losing the highest-signal token in
    the claim.
    """

    @pytest.mark.parametrize("claim,acronym", [
        ("Vaccines cause autism according to a 2019 WHO study.", "WHO"),
        ("The Earth is flat and NASA has been hiding it.", "NASA"),
        ("Drinking bleach cures COVID-19 within 24 hours.", "COVID-19"),
        ("5G towers spread the coronavirus through radio waves.", "5G"),
    ])
    def test_acronyms_are_kept(self, claim, acronym):
        assert acronym.lower() in entity_query(claim).lower()


class TestQueryShape:
    def test_it_never_returns_nothing_for_real_text(self):
        """An empty query silently skips the reference-work sources."""
        assert entity_query("Humans only use ten percent of their brains.").strip()

    def test_empty_input_is_handled(self):
        assert focus_terms("") == []
        assert focus_terms("   ") == []

    def test_punctuation_does_not_leak_into_the_query(self):
        query = entity_query("5G towers spread the coronavirus through radio waves.")
        assert "." not in query and "," not in query

    def test_the_query_is_bounded(self):
        long_claim = " ".join(f"Word{i} assertion about something" for i in range(80))
        assert len(focus_terms(long_claim)) <= 6

    def test_assertion_verbs_are_not_the_subject(self):
        """
        "causes" and "cures" describe the claim being made, not what it is
        about; including them retrieves every article making any causal
        claim.
        """
        terms = [t.lower() for t in focus_terms("Smoking tobacco causes lung cancer.")]
        assert "causes" not in terms


# ══════════════════════════════════════════════════════════════
# Fraud signals
# ══════════════════════════════════════════════════════════════

BENIGN = [
    "The central bank raised its benchmark interest rate by half a percentage "
    "point on Thursday, citing persistent inflation across the services sector.",

    "Water is an inorganic compound with the chemical formula H2O. It is the "
    "main constituent of the Earth's hydrosphere and of all known living organisms.",

    "Researchers at the University of Cambridge published findings in Nature "
    "this week showing the enzyme reduces plastic degradation time substantially.",

    "Early data suggests a possible association between the two variables, "
    "although the sample was small and the authors caution against conclusions.",
]

MANIPULATIVE = [
    "SHOCKING! Doctors don't want you to know this miracle cure! Studies show "
    "97% of people saw results in days. Act now before it's too late - big "
    "pharma is trying to get this censored! Share this before they delete it!!",

    "Guaranteed returns with ZERO risk! Double your money in 30 days with this "
    "crypto opportunity. Only 12 spots remaining - hurry! Thousands of people "
    "are already getting rich. Send bitcoin today to secure your place.",

    "Wake up! The mainstream media won't tell you the truth about what they're "
    "hiding. Do your own research - the government has been covering this up "
    "for decades. They don't want you to know. Share before it's censored!",
]


class TestFraudSeparation:
    @pytest.mark.parametrize("text", BENIGN)
    def test_honest_prose_scores_clean(self, text):
        """
        Wire copy, encyclopedia prose and hedged science reporting must not
        register. A false positive here would attach a fraud warning to
        exactly the writing the product wants people to trust.
        """
        score, _ = score_text(text)
        assert score < FLAG_THRESHOLD, f"false positive at {score}"

    @pytest.mark.parametrize("text", MANIPULATIVE)
    def test_manipulative_prose_is_flagged(self, text):
        score, fired = score_text(text)
        assert score >= FLAG_THRESHOLD, f"missed at {score}"
        assert len(fired) >= 2

    def test_the_bands_do_not_overlap(self):
        """The threshold has to sit in empty space, not between neighbours."""
        worst_benign = max(score_text(t)[0] for t in BENIGN)
        best_manipulative = min(score_text(t)[0] for t in MANIPULATIVE)
        assert worst_benign < best_manipulative
        assert worst_benign < FLAG_THRESHOLD <= best_manipulative


class TestFraudScoring:
    def test_pushy_marketing_is_not_fraud(self):
        """
        Urgency alone is ordinary commerce. An earlier scoring pass let one
        saturated signal reach 0.85 -- above the conspiracy sample -- which
        would have flagged every sale as a scam.
        """
        score, fired = score_text(
            "Limited time offer on our annual plan. Don't miss out - this deal "
            "expires today. Thousands of customers have already upgraded now."
        )
        assert len(fired) <= 2
        assert score < FLAG_THRESHOLD, f"marketing flagged as fraud at {score}"

    def test_breadth_outweighs_repetition(self):
        """Several techniques at once is the signal, not one used loudly."""
        repeated, _ = score_text("Act now! Hurry! Don't wait! Limited time! Act fast now!")
        varied, _ = score_text(
            "Act now before it's too late. Doctors don't want you to know this. "
            "Guaranteed risk-free returns await you today."
        )
        assert varied > repeated

    def test_short_text_is_not_scored(self):
        """Two emotive words in a six-word sentence is not a pattern."""
        assert score_text("Shocking news today!")[0] == 0.0

    def test_the_signals_are_returned_with_the_score(self):
        """A number nobody can audit is not a finding."""
        _, fired = score_text(MANIPULATIVE[0])
        assert fired
        for signal in fired:
            assert {"signal", "label", "strength"} <= set(signal)

    def test_the_score_is_bounded(self):
        score, _ = score_text(" ".join(MANIPULATIVE))
        assert 0.0 <= score <= 1.0


class TestFraudInTheReport:
    def test_it_runs_and_is_reported(self, client, auth):
        response = client.post(
            "/api/v1/analyze",
            data={
                "text": MANIPULATIVE[0],
                "language": "en",
            },
            headers=auth,
        )
        assert response.status_code == 200

        detectors = {d["name"]: d for d in response.json()["detectors"]}
        assert "fraud_signals" in detectors

        fraud = detectors["fraud_signals"]
        assert fraud["status"] == "ok"
        assert fraud["score"] >= FLAG_THRESHOLD
        # The signals are named, so a reader can disagree with the reasoning
        # rather than only with the number.
        assert "signals:" in (fraud["detail"] or "")


# ══════════════════════════════════════════════════════════════
# Provider visibility
# ══════════════════════════════════════════════════════════════

class TestProviderVisibility:
    def test_health_reports_which_evidence_sources_are_reachable(self, client):
        """
        The retriever skips unconfigured providers silently. Without this an
        operator cannot tell a deployment running on keyless fallbacks from
        a fully configured one, and the reports look identical while resting
        on a fraction of the evidence.
        """
        evidence = client.get("/api/v1/health").json()["evidence"]
        assert "search" in evidence and "llm" in evidence

        search = evidence["search"]
        assert isinstance(search["degraded"], bool)
        assert search["detail"]
        # The keyless providers are always attempted.
        assert "wikipedia" in search["active"]

    def test_a_missing_provider_says_what_it_would_need(self, client):
        """"Add a key" is not actionable without naming which one."""
        for entry in client.get("/api/v1/health").json()["evidence"]["search"]["missing"]:
            assert entry["requires"]
            assert entry["contributes"]

    def test_no_keyed_search_is_reported_as_degraded(self, client):
        """
        The test environment configures no search keys, so this is the
        degraded path -- and it must not report itself as healthy.
        """
        body = client.get("/api/v1/health").json()
        if body["evidence"]["search"]["keyed_active"] == 0:
            assert body["evidence"]["search"]["degraded"] is True
            assert body["status"] == "degraded"
