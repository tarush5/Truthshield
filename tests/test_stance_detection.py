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


class TestScopeMismatch:
    """A universal claim needs evidence that is itself universal in scope."""

    CLAIM = "The Indian government announced free electricity for every citizen"

    @pytest.mark.parametrize("evidence", [
        "Telangana government announces free electricity for Ganesh pandals",
        "200 Units Free Electricity for AAY Families",
        "Nitish Kumar's big move: 125 units of free electricity",
    ])
    def test_narrower_programme_is_not_support(self, evidence):
        # Regression: these corroborated a fabricated universal claim and
        # returned LIKELY TRUE at trust 78 — a fabrication asserted as true,
        # which is the most damaging direction this system can fail in.
        assert VerdictEngine._scope_mismatch(self.CLAIM, evidence) is True

    def test_matching_universal_scope_is_support(self):
        assert VerdictEngine._scope_mismatch(
            self.CLAIM,
            "India announces universal free electricity for all citizens nationwide",
        ) is False

    def test_non_universal_claim_is_unaffected(self):
        # The guard must not touch ordinary claims.
        assert VerdictEngine._scope_mismatch(
            "Paris is the capital of France", "Paris is the capital of France"
        ) is False
        assert VerdictEngine._scope_mismatch(
            "Smoking tobacco causes lung cancer", "How smoking causes lung cancer"
        ) is False


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


class TestTypographicApostrophes:
    """
    Headlines use U+2019, and the word tokenizer only accepts [a-zA-Z'], so
    "won’t" split into "won" + "t" and never matched the negation list.
    """

    @pytest.mark.parametrize("apostrophe", ["'", "\u2019", "\u02bc"])
    def test_contraction_negation_is_detected(self, apostrophe):
        evidence = f"Garlic and bleach won{apostrophe}t cure coronavirus"
        assert negates("Drinking bleach cures COVID-19 within 24 hours.", evidence) is True

    @pytest.mark.parametrize("apostrophe", ["'", "\u2019"])
    def test_doesnt_is_detected(self, apostrophe):
        evidence = f"The study doesn{apostrophe}t show vaccines cause autism"
        assert negates("Vaccines cause autism", evidence) is True


class TestInflectionMatching:
    """
    Evidence rarely repeats a claim's exact inflection. The claim says "cures",
    the headline says "cure"; without stemming the negation scan looked for
    "cures" in "...won't cure coronavirus" and found nothing, so an explicit
    debunk registered as neutral.
    """

    def test_singular_evidence_matches_plural_claim(self):
        assert negates(
            "Drinking bleach cures COVID-19",
            "Bleach does not cure COVID-19",
        ) is True

    def test_participle_evidence_matches_base_claim(self):
        assert negates(
            "The moon landing was staged",
            "The moon landings were not staged",
        ) is True

    def test_stem_is_stable_across_a_word_family(self):
        stem = VerdictEngine._stem
        for family in [
            ("cure", "cures", "cured", "curing"),
            ("cause", "causes", "caused", "causing"),
            ("land", "landing", "landings", "landed"),
            ("box", "boxes"),
            ("study", "studies"),
        ]:
            assert len({stem(w) for w in family}) == 1, family

    def test_stemming_does_not_invent_negations(self):
        # Over-stemming would collapse unrelated words and manufacture
        # refutations, which is the costlier error of the two.
        assert negates(
            "Smoking tobacco causes lung cancer",
            "Bleach is a household disinfectant used for cleaning surfaces",
        ) is False
