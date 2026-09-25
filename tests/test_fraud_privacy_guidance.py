"""
Personal data masking, safety guidance, and the email detector.

The redaction tests cut both ways deliberately. Missing a card number is a
privacy failure; masking an order reference is an information failure, and
the second is the one that gets shipped by accident because nobody tests
for it.
"""

import pytest

from truthshield.fraud import analyze
from truthshield.fraud.contract import FraudCategory
from truthshield.fraud.guidance import catalogue, for_category
from truthshield.fraud.privacy import redact


SCAM = (
    "Dear customer, your SBI KYC has expired. Your account will be blocked "
    "today. Update immediately at http://sbi-kyc-verify.secure-login.tk/update"
)

BEC_EMAIL = """From: "Rajesh Kumar CEO" <r.kumar.ceo@gmail.com>
Reply-To: accounts.payable@rk-industries-finance.tk
Subject: Urgent wire transfer needed

Are you at your desk? I am travelling and cannot talk right now.
Our bank details have changed. Please process an urgent transfer today
and keep this confidential between us."""

GENUINE_EMAIL = """From: "Jane Patel" <jane.patel@acmecorp.com>
Subject: Notes from Tuesday

Hi, attaching the notes from our meeting. Let me know if anything is missing.
Best regards, Jane"""


# ══════════════════════════════════════════════════════════════
# Personal data
# ══════════════════════════════════════════════════════════════

class TestPiiRedaction:
    """
    People reporting a scam paste the scam and everything around it -- their
    own card number, the code they nearly sent. The submission is often a
    richer source of their data than anything they would knowingly upload.
    """

    def test_a_card_number_is_masked_but_recognisable(self):
        safe, found = redact("My card 4539 1488 0343 6467 was charged today.")
        assert "4539" not in safe
        assert "6467" in safe, "last four kept so the owner can identify the card"
        assert any(r.kind == "card" for r in found)

    def test_a_one_time_code_is_masked(self):
        safe, found = redact("Your OTP is 448312. Do not share it with anyone.")
        assert "448312" not in safe
        assert any(r.kind == "otp" for r in found)

    def test_an_order_reference_is_not_mistaken_for_an_account(self):
        """
        A false redaction destroys the reference the user came in with. A
        16-digit order number failing Luhn is not a card, and a bare digit
        run with no context is not a bank account.
        """
        safe, found = redact("Order reference 1234567890123456 shipped yesterday.")
        assert "1234567890123456" in safe
        assert not found

    def test_a_phone_is_labelled_a_phone(self):
        _, found = redact("Call me back on 9876543210 when you can.")
        assert {r.kind for r in found} == {"phone"}

    def test_an_account_number_needs_context_and_then_wins(self):
        _, found = redact("Transfer to account 50100234567890 before Friday.")
        assert any(r.kind == "account" for r in found)

    def test_ordinary_text_is_untouched(self):
        original = "Nothing sensitive here, just a sentence about the weather."
        safe, found = redact(original)
        assert safe == original
        assert not found

    def test_masking_is_one_way(self):
        """There is no unmask path by design."""
        from truthshield.fraud import privacy

        assert not hasattr(privacy, "unmask")
        assert not hasattr(privacy, "restore")

    def test_the_analysis_returns_a_masked_copy(self):
        result = analyze(
            "Your KYC expired. Card 4539 1488 0343 6467 blocked. "
            "Update at http://sbi-verify.tk/kyc"
        )
        assert "4539 1488" not in result["privacy"]["redacted_content"]
        assert result["privacy"]["redactions"]
        # The limits of pattern-based masking are stated, not implied.
        assert "may miss" in result["privacy"]["note"]

    def test_detectors_still_see_the_original(self):
        """
        Masking protects what is stored and shared. Masking the input before
        analysis would blind the detectors to the thing being reported.
        """
        result = analyze(
            "Your KYC expired. Card 4539 1488 0343 6467 blocked. "
            "Update at http://sbi-verify.tk/kyc"
        )
        assert result["risk_score"] > 0


# ══════════════════════════════════════════════════════════════
# Safety guidance
# ══════════════════════════════════════════════════════════════

class TestGuidance:
    def test_every_analysis_carries_advice(self):
        guidance = analyze(SCAM)["guidance"]
        assert guidance["headline"]
        assert guidance["do_now"] and guidance["do_not"]

    def test_advice_differs_by_category(self):
        """
        The right response diverges: ignore a prize scam, but phone the bank
        about an account warning. Identical advice makes the category useless.
        """
        prize = for_category(FraudCategory.LOTTERY_PRIZE).headline
        bank = for_category(FraudCategory.BANK_IMPERSONATION).headline
        assert prize != bank

    def test_every_category_covers_the_already_happened_case(self):
        """
        Most people look this up *after* acting, and "what if I already paid"
        is the question they actually arrived with.
        """
        for entry in catalogue():
            assert entry["if_already_acted"], entry["category"]

    def test_an_unknown_category_still_gets_usable_advice(self):
        fallback = for_category(FraudCategory.UNKNOWN)
        assert fallback.headline and fallback.do_now

    def test_romance_guidance_does_not_accuse_a_person(self):
        """
        The finding is about patterns in messages, not a verdict on someone's
        partner. Being wrong about that causes real harm.
        """
        guidance = for_category(FraudCategory.ROMANCE_SCAM)
        text = " ".join(guidance.do_now + guidance.if_already_acted).lower()
        assert "scammer" not in text

    def test_guidance_is_not_alarmist(self):
        """
        Someone reading this may already have sent money, and panic produces
        worse decisions than the scam did.
        """
        for entry in catalogue():
            joined = " ".join(entry["do_now"] + entry["if_already_acted"]).lower()
            for shout in ("!!!", "immediately!!!", "you have been robbed"):
                assert shout not in joined

    def test_the_safety_centre_is_public(self, client):
        response = client.get("/api/v1/fraud/safety")
        assert response.status_code == 200
        assert response.json()["categories"]

    def test_a_single_category_can_be_fetched(self, client):
        body = client.get("/api/v1/fraud/safety?category=PHISHING").json()
        assert body["category"] == "PHISHING"
        assert body["do_not"]

    def test_an_unknown_category_is_a_404(self, client):
        assert client.get("/api/v1/fraud/safety?category=NOPE").status_code == 404


# ══════════════════════════════════════════════════════════════
# Email fraud
# ══════════════════════════════════════════════════════════════

class TestEmailFraud:
    @staticmethod
    def _codes(result):
        return {
            i["code"]
            for f in result["findings"] if f["detector"] == "email_fraud"
            for i in f["indicators"]
        }

    def test_business_email_compromise_is_caught(self):
        result = analyze(BEC_EMAIL)
        assert result["risk_level"] in ("HIGH", "CRITICAL")
        assert "replyto_mismatch" in self._codes(result)

    def test_reply_to_divergence_is_explained_not_just_flagged(self):
        """A reply lands with whoever owns that second domain, and the finding has to say so."""
        result = analyze(BEC_EMAIL)
        indicator = next(
            i for f in result["findings"] if f["detector"] == "email_fraud"
            for i in f["indicators"] if i["code"] == "replyto_mismatch"
        )
        assert indicator["evidence"]
        assert "rk-industries-finance.tk" in indicator["evidence"]

    def test_an_institution_on_free_mail_is_flagged(self):
        result = analyze(
            'From: "Microsoft Security Team" <no-reply@outlook.com>\n'
            "Subject: Unusual sign-in activity\n\n"
            "Your account will be suspended unless you verify your identity."
        )
        assert "institution_on_free_mail" in self._codes(result)

    def test_an_ordinary_work_email_is_clean(self):
        assert analyze(GENUINE_EMAIL)["risk_score"] < 15

    def test_authentication_is_declared_unchecked(self):
        """
        SPF/DKIM/DMARC live in headers a webmail client does not show.
        Without them a forged sender cannot be told from a real one, and the
        finding must say so rather than imply a verdict.
        """
        result = analyze(BEC_EMAIL)
        finding = next(f for f in result["findings"] if f["detector"] == "email_fraud")
        assert any("SPF" in limit for limit in finding["limitations"])

    def test_header_parsing_handles_a_body_with_no_headers(self):
        """Classified as email by markers, but with nothing to parse."""
        result = analyze("Dear Sir, kind regards, please see attached. Best regards.")
        assert isinstance(result["risk_score"], float)
