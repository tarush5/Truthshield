"""
Detector accuracy on the labelled evaluation sets in tests/eval/.

These sets were written for this project: invented scam and benign messages,
emails and URLs, in English, Hindi, Hinglish and Tamil. They guard against
regressions in the rules; they are not a measure of real-world accuracy.

- fraud_eval.jsonl     used to develop the rules
- fraud_holdout.jsonl  first unseen set; later used to fix general error classes
- fraud_blind.jsonl    second unseen set. Measured before any change was made
                       for it: precision 1.00, recall 0.77, false-positive
                       rate 0.00 (the 1.x rules: 1.00 / 0.35 / 0.00)
- fraud_blind2.jsonl   third unseen set, written after the blind set was used.
                       Measured before any change for it: precision 0.95,
                       recall 0.71, false-positive rate 0.04
"""

from pathlib import Path

import pytest

from truthshield.investigations.evaluation import assess, evaluate, load
from truthshield.investigations.url_features import brand_similarity

EVAL = Path(__file__).parent / "eval"


@pytest.mark.parametrize("name", ["fraud_eval", "fraud_holdout", "fraud_blind", "fraud_blind2"])
def test_eval_set_holds(name):
    report = evaluate(load(EVAL / f"{name}.jsonl"))
    errors = "\n".join(
        f"{'missed' if o.label == 'fraud' else 'false alarm'}: {o.id} {o.score} {o.level} {o.top_signals}"
        for o in report["errors"]
    )
    assert report["recall"] >= 0.95, errors
    assert report["false_positive_rate"] <= 0.04, errors


def test_final_blind_set_holds_its_measured_level():
    """
    The final blind set is never tuned on (see tests/eval/README.md), so it
    is held at the level first measured, not at perfection: precision 0.971,
    recall 0.943, false-positive rate 0.033 (65 items, 20 October 2026).
    """
    report = evaluate(load(EVAL / "fraud_final_blind.jsonl"))
    assert report["recall"] >= 0.94 and report["precision"] >= 0.97
    assert report["false_positive_rate"] <= 0.034


def _item(content, type="message"):
    return {"id": "t", "type": type, "label": "benign", "content": content}


class TestContext:
    def test_a_warning_not_to_share_an_otp_is_not_a_request(self):
        o = assess(_item("482913 is your OTP. Do not share this OTP with anyone. The bank never asks for it."))
        assert not o.flagged and "scam_payment_scam" not in o.top_signals

    def test_awareness_messages_are_not_the_scam_they_describe(self):
        o = assess(_item("Beware of digital arrest scams. Police never question anyone over video calls."))
        assert not o.flagged

    def test_a_completed_kyc_is_not_a_kyc_threat(self):
        assert not assess(_item("Your KYC has been successfully updated. Thank you for banking with us.")).flagged

    def test_a_delivery_otp_for_the_courier_is_routine(self):
        o = assess(_item("Your order arrives today. Share OTP 4417 with the delivery agent at the time of delivery."))
        assert not o.flagged

    def test_a_warning_about_fake_messages_is_not_the_scam(self):
        o = assess(_item("Scammers are sending fake electricity disconnection messages. Never call personal numbers."))
        assert not o.flagged

    def test_no_fee_is_a_negation_but_no_next_of_kin_is_not(self):
        assert not assess(_item("Shop the festive sale with no processing fee on EMI at our stores.")).flagged
        o = assess(_item("A deceased client left an unclaimed deposit and has no next of kin. Send your bank details."))
        assert o.flagged


class TestPatterns:
    @pytest.mark.parametrize("text", [
        "Aaj raat 10 baje aapki bijli kaat di jayegi. Bill update nahi hua hai, turant call kare 9123400000",
        "Hi Mum, I dropped my phone and this is my new number. Can you transfer 45000 today? Don't call.",
        "I need you to buy 5 Google Play gift cards and send me the codes, I am in a meeting.",
        "Earn 3000 daily from home by liking YouTube videos. Contact HR on Telegram.",
        "Your loan of Rs 3,00,000 is approved! To release the amount, pay the file charge of Rs 3,499 today.",
        "I have recorded your video call. Pay Rs 50,000 within 24 hours or I will send the video to all your contacts.",
        "मैं सीबीआई अधिकारी बोल रहा हूँ। आपके आधार से मनी लॉन्ड्रिंग का केस दर्ज हुआ है। तुरंत पैसे ट्रांसफर करें।",
    ])
    def test_common_scripts_are_flagged(self, text):
        assert assess(_item(text)).flagged


class TestLookalikes:
    @pytest.mark.parametrize("label, brand", [
        ("faceb00k-security-check.com", "facebook"),
        ("netf1ix-account.com", "netflix"),
        ("instagrarn-verify.com", "instagram"),
    ])
    def test_digit_and_letter_swaps_are_read_as_the_brand(self, label, brand):
        match = brand_similarity(label)
        assert match.closest == brand and match.similarity >= 0.9

    def test_doubled_letters_are_read_as_the_brand(self):
        assert brand_similarity("flipkarrt-offers.com").closest == "flipkart"

    def test_a_short_link_named_after_a_bank_is_flagged(self):
        o = assess({"id": "t", "type": "url", "label": "fraud", "content": "https://tinyurl.com/sbi-kyc-update"})
        assert "shortener_names_brand" in o.top_signals

    def test_new_brands_do_not_fuzzy_match_ordinary_words(self):
        # "mantra" is one letter from "myntra"; an edit-distance match would
        # flag a legitimate yoga shop.
        assert brand_similarity("mantra.com").closest != "myntra"
