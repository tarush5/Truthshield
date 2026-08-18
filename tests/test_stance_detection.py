"""
Stance / negation detection tests.

These pin behaviour that a live-search benchmark cannot pin reliably: evidence
comes from whatever the web returns that minute, so an end-to-end run cannot
distinguish a real regression here from search noise. The cases below are the
ones that were observed producing wrong verdicts in practice.
"""

import pytest

from backend.factcheck.verdict_engine import VerdictEngine


negates = VerdictEngine._negates_claim


class TestAdditiveConstructions:
    """"not only X" adds to X — it does not deny X."""

    @pytest.mark.parametrize("evidence", [
        "Lung cancer is not only about smoking: doctor explains the risks",
        "Lung cancer is not just caused by smoking",
        "Heart disease is not solely caused by smoking",
        "Smoking is not the only cause of lung cancer",
    ])
    def test_additive_is_not_refutation(self, evidence):
        # Regression: these were read as refuting, so articles that agree with
        # "smoking tobacco causes lung cancer" were counted as evidence against
        # it and the claim came back LIKELY FALSE.
        assert negates("Smoking tobacco causes lung cancer", evidence) is False

    def test_hedged_always_is_not_refutation(self):
        assert negates(
            "Water boils at 100 degrees Celsius",
            "Water does not always boil at 100 degrees Celsius",
        ) is False


class TestRealNegation:
    """Genuine contradictions must still register."""

    @pytest.mark.parametrize("claim,evidence", [
        ("Smoking tobacco causes lung cancer",
         "Smoking does not cause lung cancer, study claims"),
        ("The Moon is made of cheese",
         "The Moon is not made of cheese"),
        ("Vaccines cause autism",
         "Vaccines do not cause autism"),
        ("5G towers spread coronavirus",
         "5G towers do not spread coronavirus"),
    ])
    def test_direct_negation_detected(self, claim, evidence):
        assert negates(claim, evidence) is True


class TestNonNegation:
    """Plain agreeing prose is not a negation."""

    @pytest.mark.parametrize("claim,evidence", [
        ("Smoking tobacco causes lung cancer", "How smoking causes lung cancer"),
        ("Paris is the capital of France", "Paris is the capital and largest city of France"),
    ])
    def test_agreement_is_not_negation(self, claim, evidence):
        assert negates(claim, evidence) is False

    def test_unrelated_negation_elsewhere_is_ignored(self):
        # A negation far from any of the claim's own terms says nothing about it.
        assert negates(
            "Paris is the capital of France",
            "Paris hosted the Olympics. Tickets were not cheap that summer.",
        ) is False
