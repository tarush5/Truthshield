"""
Regression tests for scoring integrity.

Each case here corresponds to a defect found by running the stack and probing
it, where the system reported more confidence than it had earned. They are kept
separate from test_pipeline.py because they assert on what the product is
allowed to *claim*, not on how a given module computes.
"""

import pytest

from backend.config import UNKNOWN_DOMAIN_SCORE, score_domain
from backend.factcheck.source_ranker import SourceRanker
from backend.models.schemas import (
    AIContentResult,
    ContentPacket,
    ContentType,
    DeepfakeResult,
    Language,
    TextClassificationResult,
)
from backend.pipeline.result_aggregator import ResultAggregator


# ═══════════════════════════════════════════════
# Domain credibility must match at label boundaries
# ═══════════════════════════════════════════════

class TestDomainMatchingIsAnchored:
    """
    Scoring used a naked substring test (`known_domain in domain`). Because
    "gov" is a key worth 1.0, every host merely *containing* those letters was
    scored as an authoritative government source.
    """

    @pytest.mark.parametrize("url", [
        "https://govtjobsalert.blogspot.com/post",   # scored 1.0
        "https://thegovernor.com/news",              # scored 1.0
        "https://www.mygov-scam.tk/article",         # scored 1.0
        "https://government-news-daily.info/x",      # scored 1.0
    ])
    def test_gov_substring_is_not_a_government_source(self, url):
        assert score_domain(url) < 0.6

    def test_wire_service_substring_is_not_the_wire_service(self):
        # "pti.in" (Press Trust of India, 0.93) matched pti.industries.com.
        assert score_domain("https://pti.industries.com/x") == UNKNOWN_DOMAIN_SCORE

    @pytest.mark.parametrize("url,expected", [
        ("https://pib.gov.in/release/1", 1.0),
        ("https://cdc.gov/page", 0.98),
        ("https://www.reuters.com/world", 0.95),
        ("https://en.m.wikipedia.org/wiki/Water", 0.65),
    ])
    def test_real_domains_still_score(self, url, expected):
        """Anchoring must not break genuine matches, including subdomains."""
        assert score_domain(url) == expected

    def test_most_specific_entry_wins(self):
        # factcheck.afp.com is a fact-checker (0.95), not just AFP (0.93).
        assert score_domain("https://factcheck.afp.com/story") == 0.95

    def test_path_qualified_entry_requires_the_path(self):
        assert score_domain("https://thequint.com/news/webqoof/story") == 0.93
        assert score_domain("https://thequint.com/entertainment/x") == UNKNOWN_DOMAIN_SCORE

    def test_disinfo_domains_are_zeroed(self):
        assert score_domain("https://infowars.com/x") == 0.0
        assert score_domain("https://sub.naturalnews.com/x") == 0.0


class TestScorersAgree:
    """
    SourceRanker and EvidenceRetriever each carried their own copy of this
    logic with different defaults (0.30 vs 0.50) and different TLD tiers, while
    SourceRanker.rank_evidence overwrites whatever the retriever assigned.
    """

    @pytest.mark.parametrize("url", [
        "https://randomsite.xyz/a",
        "https://cdc.gov/a",
        "https://mit.edu/a",
        "https://some.org/a",
        "https://news.google.com/rss/a",
    ])
    def test_ranker_and_retriever_return_the_same_score(self, url):
        from backend.factcheck.evidence_retriever import EvidenceRetriever
        assert SourceRanker().score_source(url) == EvidenceRetriever._score_source(url)

    def test_demoted_tiers_rank_below_unknown_domains(self):
        """
        The config comments describe tiers 8-10 as sitting below the unknown
        default. Against the old 0.30 default that was inverted.
        """
        unknown = score_domain("https://nobody-has-heard-of-this.xyz/a")
        for demoted in (
            "https://news.google.com/rss/a",   # aggregator shell
            "https://nypost.com/a",            # tabloid
            "https://reddit.com/r/x",          # user-generated
            "https://theonion.com/a",          # satire
        ):
            assert score_domain(demoted) < unknown, demoted


# ═══════════════════════════════════════════════
# The report may not claim more than it checked
# ═══════════════════════════════════════════════

class _Ctx:
    """Minimal stand-in for PipelineContext — the aggregator only reads attrs."""

    def __init__(self, **kw):
        self.packet = kw.get("packet")
        self.claim_verdicts = kw.get("claim_verdicts", [])
        self.text_classification = kw.get("text_classification")
        self.deepfake_result = kw.get("deepfake_result")
        self.voice_clone_result = kw.get("voice_clone_result")
        self.ai_content_result = kw.get("ai_content_result")
        self.evidence_map = kw.get("evidence_map", {})
        self.social_signals = kw.get("social_signals", [])
        self.is_crisis = kw.get("is_crisis", False)
        self.input_url = kw.get("input_url")
        self.content_type = kw.get("content_type", ContentType.TEXT)


def _empty_image_context():
    """
    An image upload where nothing could be analyzed: OCR found no text and the
    deepfake model failed to load, so its result is the all-zero default.
    """
    return _Ctx(
        packet=ContentPacket(content_type=ContentType.IMAGE, lang=Language.EN, text=None),
        claim_verdicts=[],
        deepfake_result=DeepfakeResult(),  # method defaults to "unavailable"
    )


class TestNothingCheckedMeansNoVerdict:
    """
    With no claims, the aggregator promoted the ML *manipulation* score into
    support_score, which _determine_verdict reads as evidence that the content
    is true. Detectors fail open (a missing torch yields confidence 0.0 ->
    "perfectly clean"), so an image whose OCR, captioning and deepfake model had
    all failed came back VERIFIED at 85 trust with nothing verified at all.
    """

    def test_unanalyzable_content_is_not_verified(self):
        result = ResultAggregator().aggregate(_empty_image_context())
        assert result.verdict == "INSUFFICIENT EVIDENCE"
        assert result.trust_score <= 55

    def test_unanalyzable_content_says_why(self):
        result = ResultAggregator().aggregate(_empty_image_context())
        assert any("no claim was fact-checked" in r.lower() for r in result.risk_factors)

    def test_clean_detectors_alone_cannot_verify_a_claim(self):
        """
        Detectors reporting "no manipulation" is not evidence a claim is true.
        Even with every detector reporting pristine content, the verdict must
        stay INSUFFICIENT EVIDENCE while no claim has been checked.
        """
        ctx = _Ctx(
            packet=ContentPacket(content_type=ContentType.TEXT, lang=Language.EN, text="Some text."),
            claim_verdicts=[],
            text_classification=TextClassificationResult(label="real", confidence=0.99),
            deepfake_result=DeepfakeResult(confidence=0.0, method="efficientnet_b4"),
            ai_content_result=AIContentResult(ai_generated_probability=0.0),
        )
        result = ResultAggregator().aggregate(ctx)
        assert result.verdict == "INSUFFICIENT EVIDENCE"


class TestNoFabricatedReassurance:
    """
    verdict_reasons unconditionally appended "No contradicting visual deepfake
    or anomalies detected" and "Voice authenticity verified (no cloning
    detected)" — including for text-only submissions, which have no video or
    audio to clear.
    """

    def test_text_only_claims_no_video_check(self):
        ctx = _Ctx(
            packet=ContentPacket(content_type=ContentType.TEXT, lang=Language.EN, text="Some text."),
            claim_verdicts=[],
        )
        reasons = " ".join(ResultAggregator().aggregate(ctx).verdict_reasons).lower()
        assert "deepfake" not in reasons

    def test_text_only_claims_no_voice_check(self):
        ctx = _Ctx(
            packet=ContentPacket(content_type=ContentType.TEXT, lang=Language.EN, text="Some text."),
            claim_verdicts=[],
        )
        reasons = " ".join(ResultAggregator().aggregate(ctx).verdict_reasons).lower()
        assert "voice" not in reasons

    def test_unavailable_detector_does_not_report_a_clean_check(self):
        reasons = " ".join(ResultAggregator().aggregate(_empty_image_context()).verdict_reasons)
        assert "No contradicting visual deepfake" not in reasons

    def test_detector_that_ran_does_report(self):
        ctx = _Ctx(
            packet=ContentPacket(content_type=ContentType.IMAGE, lang=Language.EN, text="x"),
            claim_verdicts=[],
            deepfake_result=DeepfakeResult(confidence=0.1, method="efficientnet_b4"),
        )
        reasons = " ".join(ResultAggregator().aggregate(ctx).verdict_reasons)
        assert "No contradicting visual deepfake" in reasons


class TestUnavailableDetectorIsNotACleanScore:
    """
    _compute_ml_model_score turned a detector that never ran (confidence 0.0)
    into a 1.0 "perfectly clean" contribution, inflating manipulation_risk to a
    reported 0%.
    """

    def test_unavailable_deepfake_is_excluded_from_ml_average(self):
        result = ResultAggregator().aggregate(_empty_image_context())
        assert "deepfake_detector" not in result.component_scores
        # Neutral, not a falsely perfect 0% risk.
        assert result.component_scores["manipulation_risk"] == 50.0


# ═══════════════════════════════════════════════
# Evidence must be attributed to whoever published it
# ═══════════════════════════════════════════════

class TestPublisherAttribution:
    """
    Google News hands back news.google.com interstitials. Scoring that URL
    rated every article as an aggregator (0.45) no matter who reported it —
    below the 0.50 floor every stance path requires — so CDC, Reuters and
    Britannica articles could not support or refute anything. Six of twelve
    benchmark claims went unverified on evidence that had in fact been
    retrieved.
    """

    def _ev(self, **kw):
        from backend.models.schemas import Evidence
        base = dict(
            title="Some headline - Reuters",
            url="https://news.google.com/rss/articles/CBMiabcdef",
            snippet="...",
            source_score=0.5,
        )
        base.update(kw)
        return Evidence(**base)

    def test_ranker_scores_the_publisher_not_the_aggregator(self):
        ev = self._ev(source_domain="https://www.reuters.com")
        SourceRanker().rank_evidence([ev])
        assert ev.source_score == 0.95

    def test_publisher_scores_clear_the_stance_floor(self):
        for domain, expected in [
            ("https://www.cdc.gov", 0.98),
            ("https://www.bbc.com", 0.92),
            ("https://www.britannica.com", 0.80),
        ]:
            ev = self._ev(source_domain=domain)
            SourceRanker().rank_evidence([ev])
            assert ev.source_score == expected, domain
            assert ev.source_score >= 0.50

    def test_falls_back_to_the_url_when_no_publisher_is_known(self):
        ev = self._ev(source_domain=None)
        SourceRanker().rank_evidence([ev])
        assert ev.source_score == 0.45   # the aggregator's own score

    def test_aggregator_score_is_not_applied_over_a_known_publisher(self):
        """A content farm behind an aggregator still scores as itself."""
        ev = self._ev(source_domain="https://www.infowars.com")
        SourceRanker().rank_evidence([ev])
        assert ev.source_score == 0.0


# ═══════════════════════════════════════════════
# A question is not an assertion
# ═══════════════════════════════════════════════

class TestInterrogativeEvidence:
    """
    Debunks are routinely headlined as the question they answer, and an
    aggregator snippet is often just that headline repeated. Read as
    assertions, they corroborated the myths they exist to correct — "Do We
    Really Use Only 10 Percent of Our Brain?" was scored as SUPPORTING
    "Humans only use ten percent of their brains".
    """

    @pytest.mark.parametrize("text", [
        "Do We Really Use Only 10 Percent of Our Brain?",
        "Do People Only Use 10 Percent of Their Brains?  Scientific American",
        "Can MMR vaccines cause autism? - Gavi, the Vaccine Alliance",
        "Does water's boiling point change with altitude? Americans aren't sure",
        "Is the Earth flat? What the evidence shows",
    ])
    def test_question_headlines_are_interrogative(self, text):
        from backend.factcheck.verdict_engine import VerdictEngine
        assert VerdictEngine._is_interrogative(text) is True

    @pytest.mark.parametrize("text", [
        "How Vaccines are Developed and Approved for Use - CDC",
        "No, 5G Didn't Cause the Coronavirus Pandemic",
        "Smoking causes lung cancer, CDC says",
        "Why eclipses are important for scientific discoveries",
        "Scientists ask: is the brain fully used? Yes, it is.",
    ])
    def test_statements_are_not_interrogative(self, text):
        from backend.factcheck.verdict_engine import VerdictEngine
        assert VerdictEngine._is_interrogative(text) is False

    def test_a_question_does_not_support_the_claim_it_poses(self):
        from backend.factcheck.verdict_engine import VerdictEngine
        from backend.models.schemas import Claim, Evidence

        claim = Claim(text="Humans only use ten percent of their brains.")
        evidence = [
            Evidence(
                title="Do We Really Use Only 10 Percent of Our Brain? - Britannica",
                url="https://www.britannica.com/story/ten-percent-brain",
                snippet="Do We Really Use Only 10 Percent of Our Brain?  britannica.com",
                source_score=0.80,
            ),
        ]
        VerdictEngine()._tfidf_evaluate(claim, evidence)
        assert evidence[0].stance != "SUPPORTS"
