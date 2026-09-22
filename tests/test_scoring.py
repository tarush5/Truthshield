"""
Scoring integrity and verdict accuracy.

Two separate concerns:

* **Integrity** — the report must never claim more than it checked. Each case
  here is a failure the previous system actually produced.
* **Accuracy** — measured against frozen evidence, so a change in the score is
  a change in the code and not in what the web returned this minute.
"""

import pytest

from truthshield.domain.credibility import UNKNOWN_DOMAIN_SCORE, score_domain
from truthshield.domain.scoring.aggregator import TrustScorer
from truthshield.domain.types import (
    Claim, ClaimVerdict, ConfidenceBand, ContentPacket, ContentType,
    DetectorResult, DetectorStatus, EvidenceItem, Language, Stance, Verdict,
)


# ══════════════════════════════════════════════════════════════
# Source credibility
# ══════════════════════════════════════════════════════════════

class TestDomainScoring:
    @pytest.mark.parametrize("url", [
        "https://govtjobsalert.blogspot.com/post",
        "https://thegovernor.com/news",
        "https://www.mygov-scam.tk/article",
    ])
    def test_a_host_merely_containing_gov_is_not_authoritative(self, url):
        """Substring matching scored all of these 1.0 — maximum government trust."""
        assert score_domain(url) < 0.6

    @pytest.mark.parametrize("url,expected", [
        ("https://pib.gov.in/release/1", 1.0),
        ("https://cdc.gov/page", 0.98),
        ("https://www.reuters.com/world", 0.95),
        ("https://en.m.wikipedia.org/wiki/Water", 0.65),
        ("https://factcheck.afp.com/story", 0.95),
    ])
    def test_real_publishers_score_correctly(self, url, expected):
        assert score_domain(url) == expected

    def test_disinformation_domains_are_zeroed(self):
        assert score_domain("https://infowars.com/x") == 0.0
        assert score_domain("https://sub.naturalnews.com/x") == 0.0

    def test_demoted_tiers_rank_below_unknown_domains(self):
        unknown = score_domain("https://nobody-has-heard-of-this.xyz/a")
        assert unknown == UNKNOWN_DOMAIN_SCORE
        for demoted in ("https://news.google.com/rss/a", "https://theonion.com/a",
                        "https://reddit.com/r/x", "https://nypost.com/a"):
            assert score_domain(demoted) < unknown, demoted


# ══════════════════════════════════════════════════════════════
# The report may not claim more than it checked
# ══════════════════════════════════════════════════════════════

def _packet(**kw):
    return ContentPacket(
        content_type=kw.pop("content_type", ContentType.TEXT),
        language=Language.EN, **kw,
    )


class TestNothingCheckedMeansNoVerdict:
    """
    The flagship failure: an image whose OCR, captioning and deepfake model had
    all failed came back VERIFIED at 85% trust. Detectors failed open, and the
    manipulation score was laundered into "sources support this claim".
    """

    def test_unanalyzable_media_is_not_verified(self):
        result = TrustScorer().score(
            _packet(content_type=ContentType.IMAGE, text=None, file_path="x.png"),
            [],
            [DetectorResult(name="deepfake", status=DetectorStatus.UNAVAILABLE,
                            detail="OpenCV is not installed")],
        )
        assert result.verdict is Verdict.INSUFFICIENT_EVIDENCE
        assert result.trust_score <= 60
        assert result.confidence_band is not ConfidenceBand.HIGH

    def test_it_says_why_nothing_could_be_checked(self):
        result = TrustScorer().score(
            _packet(content_type=ContentType.IMAGE, text=None, file_path="x.png"),
            [],
            [DetectorResult(name="deepfake", status=DetectorStatus.UNAVAILABLE, detail="missing")],
        )
        assert any("no claim was fact-checked" in r.lower() for r in result.limitations)

    def test_a_detector_that_did_not_run_leaves_risk_neutral(self):
        """
        A 0.0 score from a detector that never ran used to read as 'verified
        clean' and push the trust score up.
        """
        result = TrustScorer().score(
            _packet(content_type=ContentType.IMAGE, file_path="x.png"),
            [],
            [DetectorResult(name="deepfake", status=DetectorStatus.UNAVAILABLE)],
        )
        assert result.breakdown.manipulation_risk == 50.0

    def test_clean_detectors_alone_cannot_verify_a_claim(self):
        """"This photo isn't doctored" says nothing about whether the caption is true."""
        result = TrustScorer().score(
            _packet(text="Some text."),
            [],
            [DetectorResult(name="deepfake", status=DetectorStatus.OK, score=0.0, method="opencv"),
             DetectorResult(name="ai_text", status=DetectorStatus.OK, score=0.0, method="heuristic")],
        )
        assert result.verdict is Verdict.INSUFFICIENT_EVIDENCE

    def test_all_claims_unresolved_is_not_partially_true(self):
        """
        Claims checked but unsettled were reported as PARTIALLY TRUE at trust
        64 — a number assembled entirely from component defaults.
        """
        unresolved = ClaimVerdict(
            claim=Claim(text="Something unverifiable"),
            verdict=Verdict.INSUFFICIENT_EVIDENCE, confidence=0.2,
        )
        result = TrustScorer().score(_packet(text="x"), [unresolved], [])
        assert result.verdict is Verdict.INSUFFICIENT_EVIDENCE

    def test_detected_manipulation_still_counts_without_a_claim(self):
        """Positive evidence of tampering stands on its own."""
        result = TrustScorer().score(
            _packet(content_type=ContentType.IMAGE, file_path="x.png"),
            [],
            [DetectorResult(name="deepfake", status=DetectorStatus.OK, score=0.9, method="opencv")],
        )
        assert result.verdict is Verdict.LIKELY_FALSE


class TestNoFabricatedReassurance:
    """
    Reports asserted "No contradicting visual deepfake or anomalies detected"
    and "Voice authenticity verified" on text-only submissions, which have no
    video or audio to clear.
    """

    def test_limitations_name_the_checks_that_could_not_run(self):
        result = TrustScorer().score(
            _packet(text="x"),
            [],
            [DetectorResult(name="voice_clone", status=DetectorStatus.UNAVAILABLE,
                            detail="librosa is not installed")],
        )
        joined = " ".join(result.limitations).lower()
        assert "voice clone" in joined and "could not run" in joined

    def test_a_check_that_did_not_apply_is_not_listed_as_a_limitation(self):
        result = TrustScorer().score(
            _packet(text="x"),
            [],
            [DetectorResult(name="voice_clone", status=DetectorStatus.NOT_APPLICABLE)],
        )
        assert not any("voice" in r.lower() for r in result.limitations)


class TestVerdictFromClaims:
    def _supported(self, verdict, confidence, n_support=3):
        return ClaimVerdict(
            claim=Claim(text="c"), verdict=verdict, confidence=confidence,
            evidence=[
                EvidenceItem(title=f"s{i}", url=f"https://reuters.com/{i}",
                             source_score=0.95, stance=Stance.SUPPORTS)
                for i in range(n_support)
            ],
        )

    def test_one_false_claim_outweighs_several_true_ones(self):
        """Content containing a falsehood is not 'mostly true'."""
        claims = [
            self._supported(Verdict.VERIFIED, 0.9),
            self._supported(Verdict.VERIFIED, 0.9),
            ClaimVerdict(claim=Claim(text="bad"), verdict=Verdict.FALSE, confidence=0.9),
        ]
        result = TrustScorer().score(_packet(text="x"), claims, [])
        assert result.verdict is Verdict.FALSE

    def test_trust_score_stays_inside_its_verdict_band(self):
        for verdict, confidence in [(Verdict.VERIFIED, 0.95), (Verdict.FALSE, 0.95)]:
            claim = self._supported(verdict, confidence)
            if verdict is Verdict.FALSE:
                claim.evidence = [
                    EvidenceItem(title="r", url="https://reuters.com/x",
                                 source_score=0.95, stance=Stance.REFUTES)
                ]
            result = TrustScorer().score(_packet(text="x"), [claim], [])
            from truthshield.domain.scoring.aggregator import BANDS
            low, high = BANDS[result.verdict]
            assert low <= result.trust_score <= high

    def test_confidence_is_never_high_on_a_single_source(self):
        claim = self._supported(Verdict.LIKELY_TRUE, 0.8, n_support=1)
        result = TrustScorer().score(_packet(text="x"), [claim], [])
        assert result.confidence_band is not ConfidenceBand.HIGH


# ══════════════════════════════════════════════════════════════
# Accuracy against frozen evidence
# ══════════════════════════════════════════════════════════════

TRUEISH = {"TRUE"}
FALSEISH = {"FALSE"}
ABSTAIN = {"UNVERIFIED", "MISLEADING"}


def _score_fixture(claims):
    from truthshield.domain.verdict.engine import VerdictEngine
    from truthshield.domain.verdict.legacy_types import Claim as LClaim, Evidence as LEvidence

    correct = wrong = abstained = 0
    rows = []
    for record in claims:
        evidence = [
            LEvidence(title=e["title"], url=e["url"], snippet=e["snippet"],
                      source_score=e["source_score"])
            for e in record["evidence"]
        ]
        verdict = VerdictEngine()._tfidf_evaluate(
            LClaim(text=record["claim"]), evidence
        ).verdict.value.upper()

        expected = record["expected"]
        if verdict in ABSTAIN:
            outcome, abstained = "abstain", abstained + 1
        elif (expected == "true" and verdict in TRUEISH) or (expected == "false" and verdict in FALSEISH):
            outcome, correct = "correct", correct + 1
        else:
            outcome, wrong = "WRONG", wrong + 1
        rows.append((outcome, expected, verdict, record["claim"]))
    return correct, wrong, abstained, rows


class TestVerdictAccuracy:
    """
    Scored against `tests/fixtures/evidence_fixture.json`.

    Live search made this unmeasurable: the same build scored 6/8 and 2/8 on
    consecutive runs purely on what the web returned, with DuckDuckGo timing
    out during one of them.
    """

    def test_never_decided_in_the_wrong_direction(self, fixture_claims):
        """
        Calling a true claim false, or a false claim true, is the failure this
        product exists to avoid — worse than abstaining.
        """
        _, wrong, _, rows = _score_fixture(fixture_claims)
        misses = [r for r in rows if r[0] == "WRONG"]
        assert wrong == 0, "decided wrongly:\n" + "\n".join(
            f"  expected {e}, got {v}: {c}" for _, e, v, c in misses
        )

    def test_commits_on_enough_claims(self, fixture_claims):
        """
        Coverage floor, set just under the measured baseline (9/12). Abstaining
        everywhere would satisfy the precision test while being useless.
        """
        correct, _, abstained, rows = _score_fixture(fixture_claims)
        assert correct / len(rows) >= 0.70, (
            f"only {correct}/{len(rows)} decided correctly ({abstained} abstained):\n"
            + "\n".join(f"  [{o:<7}] {v:<12} {c[:60]}" for o, e, v, c in rows)
        )

    @pytest.mark.parametrize("direction", ["true", "false"])
    def test_both_directions_are_reachable(self, fixture_claims, direction):
        """
        Guard against a one-sided engine. An earlier build could reach FALSE
        far more easily than TRUE, because support required a TF-IDF cosine
        that snippet length made unreachable while refutation only needed a
        negation word.
        """
        subset = [c for c in fixture_claims if c["expected"] == direction]
        correct, _, _, _ = _score_fixture(subset)
        assert correct >= 2
