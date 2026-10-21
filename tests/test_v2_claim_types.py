"""Only factual claims go to public fact-checking; every sentence says why or why not."""

import pytest

from tests.test_v2_engines import ctx
from truthshield.investigations.engines.text import TextEngine


def screening(text):
    c = ctx(text)
    result = TextEngine().run(c)
    return {s["text"]: s for s in result.artifacts["claim_screening"]}, result.artifacts.get("claims", [])


@pytest.mark.parametrize("sentence,kind", [
    ("I think the new metro line is the best thing to happen to the city.", "OPINION"),
    ("In my opinion the budget favours large companies over farmers.", "OPINION"),
    ("My brother has been admitted to the hospital since Monday evening.", "PERSONAL"),
    ("Click the link below to update your details now.", "INSTRUCTION"),
])
def test_non_factual_sentences_are_typed_and_not_checked(sentence, kind):
    rows, claims = screening(sentence)
    row = next(iter(rows.values()))
    assert row["type"] == kind and row["fact_checked"] is False and row["reason"]
    assert claims == []


def test_a_factual_claim_is_checked_and_typed():
    rows, claims = screening("The World Health Organization declared the end of the mpox emergency in 2023.")
    assert claims and claims[0]["type"] == "FACTUAL"
    assert next(iter(rows.values()))["fact_checked"] is True


@pytest.mark.parametrize("sentence", [
    "I read that drinking bleach cures COVID.",
    "We heard that the RBI is withdrawing all 500 rupee notes next month.",
    "My doctor says the WHO has banned paracetamol worldwide.",
])
def test_personal_framing_of_a_public_claim_is_still_checked(sentence):
    rows, claims = screening(sentence)
    assert claims, rows
