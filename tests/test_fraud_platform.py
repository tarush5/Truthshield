"""
The fraud detection platform: contract, routing, detectors.

The tests that matter most here are the false-positive ones. A fraud tool
that cries wolf trains people to dismiss it, and a dismissed warning is
worse than no warning -- so genuine bank messages, real login pages and
ordinary conversation are asserted clean at least as carefully as the scams
are asserted dirty.
"""

import pytest

from truthshield.fraud import InputKind, analyze, catalogue, classify, extract_entities
from truthshield.fraud.contract import (
    FraudCategory, Indicator, RiskLevel, Severity, score_from_indicators,
)
from truthshield.fraud.detectors.url import inspect_url


# ── Samples ───────────────────────────────────────────────────

GENUINE = {
    "bank debit alert":
        "Your account ending 4412 was debited Rs.2,340.00 on 24-Sep at AMAZON "
        "RETAIL. Not you? Call 1800-111-109.",
    "shipping notice":
        "Your Amazon order has shipped and will arrive Thursday. Track it in "
        "the Amazon app.",
    "newsletter":
        "Thanks for subscribing. Read this week's edition at "
        "https://www.economist.com/weekly and manage preferences any time.",
    "ordinary chat":
        "Hey are we still meeting at 6? I can bring the documents you asked "
        "about yesterday.",
}

REAL_LOGIN_PAGES = [
    "https://www.hdfcbank.com/personal/netbanking/login",
    "https://www.paypal.com/signin",
    "https://mail.google.com/mail/u/0/",
    "https://github.com/login",
]

SCAMS = {
    "bank impersonation":
        "Dear customer, your SBI KYC has expired. Your account will be blocked "
        "today. Update immediately at http://sbi-kyc-verify.secure-login.tk/update",
    "delivery fee":
        "Your parcel is held at customs pending a fee of Rs.45. Pay now at "
        "http://india-post-clear.tk/pay to release your package today.",
    "investment":
        "Guaranteed 40% monthly returns, risk-free trading signals. Join our VIP "
        "group and double your money. Send USDT to start.",
    "code-switched KYC":
        "Sir aapka KYC expire ho gaya hai, turant link par click karo aur OTP "
        "share kijiye: http://kyc-update-now.ml/verify",
    "prize":
        "Congratulations! You have won Rs.25,00,000 in the lucky draw. Claim your "
        "prize now by paying the processing fee before it expires today.",
}


# ══════════════════════════════════════════════════════════════
# The output contract
# ══════════════════════════════════════════════════════════════

class TestFindingContract:
    """
    Every field that makes a finding auditable is required, not optional.

    A bare "fraud"/"not fraud" is unusable: the reader cannot tell what
    triggered it, how sure the system is, or what it failed to check.
    """

    REQUIRED = {
        "analysis_id", "detector", "category", "risk_score", "risk_level",
        "confidence", "summary", "indicators", "recommended_action",
        "limitations", "methods", "detected_at",
    }

    def test_a_finding_carries_everything_needed_to_audit_it(self):
        result = analyze(SCAMS["bank impersonation"])
        assert result["findings"]
        for finding in result["findings"]:
            assert self.REQUIRED <= set(finding), (
                f"missing: {self.REQUIRED - set(finding)}"
            )

    def test_every_indicator_carries_its_own_evidence(self):
        """A claim the reader cannot check is an assertion, not evidence."""
        result = analyze(SCAMS["code-switched KYC"])
        for finding in result["findings"]:
            for indicator in finding["indicators"]:
                assert {"code", "title", "severity", "explanation"} <= set(indicator)
                assert indicator["explanation"].strip()

    def test_limitations_are_always_present_even_when_clean(self):
        """
        An absent key reads as "nothing was missed", which is a claim of its
        own -- and for a structural URL check it is a false one.
        """
        result = analyze("https://www.bbc.co.uk/news")
        for finding in result["findings"]:
            assert "limitations" in finding

    def test_scores_are_clamped(self):
        from truthshield.fraud.contract import FraudFinding

        finding = FraudFinding(
            detector="x", category=FraudCategory.PHISHING,
            risk_score=9999, confidence=42, summary="",
        )
        assert finding.risk_score == 100.0
        assert finding.confidence == 1.0

    @pytest.mark.parametrize("score,level", [
        (0, RiskLevel.SAFE), (14, RiskLevel.SAFE), (15, RiskLevel.LOW),
        (39, RiskLevel.LOW), (40, RiskLevel.MEDIUM), (64, RiskLevel.MEDIUM),
        (65, RiskLevel.HIGH), (84, RiskLevel.HIGH), (85, RiskLevel.CRITICAL),
        (100, RiskLevel.CRITICAL),
    ])
    def test_risk_bands_are_stable(self, score, level):
        assert RiskLevel.for_score(score) is level


class TestScoreComposition:
    def test_a_single_indicator_cannot_reach_critical(self):
        """
        Breadth is what separates a scam from one unlucky phrase. The text
        fraud detector already learned this: one saturated signal previously
        put ordinary marketing above a conspiracy sample.
        """
        lone = [Indicator("x", "X", Severity.HIGH, "why", weight=3.0)]
        assert score_from_indicators(lone) < 65

    def test_more_distinct_indicators_score_higher(self):
        one = score_from_indicators([Indicator("a", "A", Severity.MEDIUM, "w")])
        three = score_from_indicators([
            Indicator("a", "A", Severity.MEDIUM, "w"),
            Indicator("b", "B", Severity.MEDIUM, "w"),
            Indicator("c", "C", Severity.MEDIUM, "w"),
        ])
        assert three > one

    def test_repetition_has_diminishing_returns(self):
        """Ten instances of one tactic is not ten times the evidence."""
        five = score_from_indicators([
            Indicator(f"i{n}", "I", Severity.MEDIUM, "w") for n in range(5)
        ])
        ten = score_from_indicators([
            Indicator(f"i{n}", "I", Severity.MEDIUM, "w") for n in range(10)
        ])
        assert ten - five < 15

    def test_nothing_observed_scores_zero(self):
        assert score_from_indicators([]) == 0.0


# ══════════════════════════════════════════════════════════════
# Input classification
# ══════════════════════════════════════════════════════════════

class TestClassification:
    def test_an_sms_with_a_link_is_both(self):
        """
        The interesting fraud lives in the relationship: the message supplies
        the pretext, the link takes the credential. One label loses that.
        """
        result = classify(SCAMS["bank impersonation"])
        assert result.has(InputKind.SMS)
        assert result.has(InputKind.URL)

    def test_email_headers_are_recognised(self):
        result = classify("From: billing@acme.co\nSubject: Invoice overdue\n\nPlease remit.")
        assert result.has(InputKind.EMAIL_MESSAGE)

    def test_entities_are_extracted(self):
        entities = extract_entities(
            "Call 9876543210 or mail fraud@bank.co, pay to scammer@okaxis, "
            "see http://evil.tk/x"
        )
        assert entities["phones"]
        assert entities["emails"]
        assert entities["urls"]
        assert entities["upi_handles"]

    def test_a_upi_handle_is_not_reported_as_an_email(self):
        entities = extract_entities("Send to merchant@okicici please")
        assert entities["upi_handles"]
        assert not entities["emails"]

    def test_empty_input_is_handled(self):
        assert classify("").primary is InputKind.TEXT
        assert analyze("")["risk_score"] == 0.0


# ══════════════════════════════════════════════════════════════
# False positives — the ones that matter most
# ══════════════════════════════════════════════════════════════

class TestGenuineContentIsNotFlagged:
    @pytest.mark.parametrize("label", sorted(GENUINE))
    def test_genuine_messages_stay_low(self, label):
        result = analyze(GENUINE[label])
        assert result["risk_score"] < 40, (
            f"{label} scored {result['risk_score']} ({result['category']})"
        )

    @pytest.mark.parametrize("url", REAL_LOGIN_PAGES)
    def test_a_real_login_page_is_not_suspicious(self, url):
        """
        A sign-in path is meaningless on its own -- every bank and mailbox
        has one. Scoring the path alone flagged hdfcbank.com's real login
        page, and a false positive there teaches people to ignore the tool.
        """
        result = analyze(url)
        assert result["risk_score"] < 15, (
            f"{url} scored {result['risk_score']}"
        )


# ══════════════════════════════════════════════════════════════
# True positives
# ══════════════════════════════════════════════════════════════

class TestScamsAreCaught:
    @pytest.mark.parametrize("label", sorted(SCAMS))
    def test_scams_are_flagged(self, label):
        result = analyze(SCAMS[label])
        assert result["risk_score"] >= 40, (
            f"{label} scored only {result['risk_score']}"
        )
        assert result["findings"]

    def test_the_category_is_identified_not_just_the_risk(self):
        """
        Category drives the safety advice, and the advice diverges: ignore a
        prize scam, but phone the bank on a printed number for an account
        warning.
        """
        assert analyze(SCAMS["delivery fee"])["category"] == "DELIVERY_SCAM"
        assert analyze(SCAMS["investment"])["category"] == "INVESTMENT_SCAM"
        assert analyze(SCAMS["bank impersonation"])["category"] in (
            "BANK_IMPERSONATION", "PHISHING",
        )

    def test_code_switched_text_is_detected(self):
        """
        Hindi-English in Latin script carries a large share of real scam
        traffic; an English-only pattern set scores it zero while a human
        reads it instantly.
        """
        result = analyze(SCAMS["code-switched KYC"])
        assert result["risk_score"] >= 65

    def test_every_scam_gets_actionable_advice(self):
        for text in SCAMS.values():
            result = analyze(text)
            assert any(f["recommended_action"].strip() for f in result["findings"])


class TestUrlStructure:
    @pytest.mark.parametrize("url,code", [
        ("https://xn--pypal-4ve.com/signin", "punycode_host"),
        ("http://paypal.secure-login.tk/verify", "brand_outside_domain"),
        ("http://192.168.10.44/account/login", "ip_host"),
        ("https://bit.ly/3xYz", "shortener"),
        ("http://evil.com@real-bank.com/login", "userinfo_in_url"),
    ])
    def test_disguises_are_detected(self, url, code):
        assert code in {i.code for i in inspect_url(url)}

    def test_a_plain_reputable_url_yields_nothing_weighted(self):
        indicators = inspect_url("https://www.reuters.com/world/article-12345")
        assert score_from_indicators(indicators) == 0.0


# ══════════════════════════════════════════════════════════════
# Registry and API
# ══════════════════════════════════════════════════════════════

class TestRegistry:
    def test_detectors_are_registered(self):
        names = {d["name"] for d in catalogue()}
        assert {"url_structure", "message_scam"} <= names

    def test_coverage_says_what_actually_ran(self):
        """
        A low score from one detector and a low score from six are different
        statements, and the caller has to be able to tell them apart.
        """
        result = analyze(SCAMS["bank impersonation"])
        coverage = result["coverage"]
        assert set(coverage) == {"ran", "not_applicable", "failed"}
        assert "message_scam" in coverage["ran"]

    def test_only_restricts_to_named_detectors(self):
        result = analyze(SCAMS["bank impersonation"], only=["url_structure"])
        assert result["coverage"]["ran"] == ["url_structure"]

    def test_a_failing_detector_is_reported_not_swallowed(self):
        """
        A detector that failed and a detector that found nothing are
        different answers; collapsing them tells the reader an input was
        cleared when it was never examined.
        """
        from truthshield.fraud.classify import Classification
        from truthshield.fraud.registry import FraudDetector

        class Broken(FraudDetector):
            name = "broken_for_test"
            handles = (InputKind.TEXT,)

            def applies_to(self, text, classification):
                return True

            def _run(self, text, classification):
                raise RuntimeError("boom")

        finding = Broken().analyze("some text here", Classification())
        assert finding is not None
        assert finding.confidence == 0.0
        assert finding.limitations


class TestFraudApi:
    def test_analysis_requires_authentication(self, client):
        assert client.post(
            "/api/v1/fraud/analyze", json={"content": "some message"},
        ).status_code == 401

    def test_the_detector_catalogue_is_served(self, client):
        names = {d["name"] for d in client.get("/api/v1/fraud/detectors").json()["detectors"]}
        assert "url_structure" in names

    def test_a_scam_is_analysed_end_to_end(self, client, auth):
        response = client.post(
            "/api/v1/fraud/analyze",
            json={"content": SCAMS["bank impersonation"]},
            headers=auth,
        )
        assert response.status_code == 200

        body = response.json()
        assert body["risk_level"] in ("MEDIUM", "HIGH", "CRITICAL")
        assert body["findings"]
        assert body["classification"]["primary"]

    def test_oversized_input_is_refused(self, client, auth):
        from truthshield.settings import get_settings

        response = client.post(
            "/api/v1/fraud/analyze",
            json={"content": "x" * (get_settings().MAX_TEXT_LENGTH + 1)},
            headers=auth,
        )
        assert response.status_code == 413
