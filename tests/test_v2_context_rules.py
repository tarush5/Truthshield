"""Context handling in the scam rules: each case has a scam and a benign twin."""

import pytest

from truthshield.fraud.registry import analyze


def codes(text):
    return {i["code"] for f in analyze(text)["findings"] for i in f["indicators"]}


def flagged(text):
    return analyze(text)["risk_score"] >= 40


@pytest.mark.parametrize("scam,benign", [
    # Negation reaches across "or": "never confirm or forward an OTP".
    ("Please forward the OTP you received to this number now.",
     "Never confirm or forward an OTP to anyone who calls you, even if they say they are the bank."),
    # "confirm the OTP" is a request only when it goes back to the sender.
    ("To stop the debit, confirm the OTP on this chat so we can reverse it right away.",
     "Enter the OTP on the website to confirm your payment of Rs 500 to the electricity board."),
    # A job offer is not a lottery.
    ("Congratulations! You have been selected to receive a free iPhone, pay Rs 99 shipping to claim.",
     "Congratulations, you have been selected for the Analyst role. Your offer letter is attached."),
    # A fee needs a job around it to be a hiring fee.
    ("You have been shortlisted for the data entry post. Pay Rs 2,000 deposit to get your appointment letter.",
     "Your daughter has been selected for the district chess team. The tournament fee of Rs 250 is due Friday."),
    # Second person wins; third person is news.
    ("Badhai ho! Aapne lucky draw mein 5 lakh jeete hain, inaam ke liye fees jama karein.",
     "Suna kya, padosi Verma ji ne Kerala lottery mein 50 lakh jeete hain, akhbaar mein aaya tha."),
    # Police reporting an arrest is news; police threatening one is a scam.
    ("Cyber crime cell here. Police have arrested your son. Transfer Rs 40,000 immediately for bail.",
     "Cyber crime police arrested three men who sent fake bank messages to residents, officials said."),
])
def test_scam_and_benign_twins(scam, benign):
    assert flagged(scam), analyze(scam)
    assert not flagged(benign), analyze(benign)


def test_disguised_keywords_are_read_and_reported():
    text = "Y0ur b@nk acc0unt is l0cked. Share the 0TP with our agent to unl0ck it."
    found = codes(text)
    assert "disguised_keywords" in found and "scam_payment_scam" in found


def test_account_numbers_and_codes_are_not_treated_as_disguise():
    text = "Rs 1,250 debited from A/c XX4521 for UPI ref 4G7H2. Avl bal Rs 18,442. Not you? Call the bank."
    assert "disguised_keywords" not in codes(text)


def test_unrequested_code_with_the_verb_first():
    assert flagged("Kindly forward that 4 digit number to me, it came to your phone by my mistake.")


@pytest.mark.parametrize("scam,benign", [
    # A negated fee is not a fee.
    ("You are shortlisted for the clerk post. Pay the joining fee of Rs 3,000 to receive your offer letter.",
     "Your offer letter for the clerk post is attached. There is no joining fee at any stage."),
    # A request followed by a PIN moves money out; asking for money back does not.
    ("I sent 1,000 to you by mistake. I raised a request, please approve it and enter your UPI PIN to return it.",
     "I think I sent you 1,000 by mistake yesterday, could you send it back when you're free?"),
    # A report about a scam never addresses the reader.
    ("Officials said your Aadhaar is linked to a money laundering case. Pay the security amount today "
     "to avoid digital arrest.",
     "Callers posing as customs officers told the man a parcel with drugs was seized and demanded money, "
     "police said on Friday."),
    # "No such thing as a digital arrest" is the warning, not the threat.
    ("This is the CBI. You are under digital arrest. Stay on the video call and transfer the funds.",
     "Remember there is no such thing as a digital arrest; hang up on anyone who says otherwise."),
])
def test_scam_and_benign_twins_cycle_four(scam, benign):
    assert flagged(scam), analyze(scam)
    assert not flagged(benign), analyze(benign)


def test_a_provider_writing_from_its_own_domain_is_not_free_mail():
    text = "From: Billing <billing@zoho.com>\nSubject: Invoice\n\nYour invoice for October is attached."
    assert "institution_on_free_mail" not in codes(text)
    spoof = "From: HDFC Bank Billing <hdfc.billing@zohomail.in>\nSubject: Invoice\n\nYour invoice is attached."
    assert "institution_on_free_mail" in codes(spoof)
