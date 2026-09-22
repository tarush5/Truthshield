"""
Accuracy of the verdict engine, scored against frozen evidence.

The end-to-end benchmark hits live search, so the same build scored 6/8 and
2/8 on consecutive runs purely on what the web returned that minute (one of
those runs had DuckDuckGo timing out entirely). That is fine as a smoke test
but useless for judging whether a change to stance detection helped.

Here the evidence is fixed — captured once by `capture_evidence_fixture.py`
from real retrieval — so the only thing that can move the score is the code.

Two properties matter, and they are not the same thing:

  * **Precision**: of the claims where the engine committed to a direction,
    how many were right. A misinformation tool that confidently says a true
    claim is false, or a false claim is true, is worse than one that abstains,
    so this is asserted at 100%.
  * **Coverage**: how often it commits at all. Abstaining on everything would
    score perfect precision and be useless, so this has a floor too.

Both thresholds sit just under the current measured values, so a real
regression fails the suite while normal drift does not.
"""

import json
from pathlib import Path

import pytest

from backend.factcheck.verdict_engine import VerdictEngine
from backend.models.schemas import Claim, Evidence

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "evidence_fixture.json"

TRUEISH = {"TRUE"}
FALSEISH = {"FALSE"}
ABSTAIN = {"UNVERIFIED", "MISLEADING"}


def _load():
    with open(FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)["claims"]


def _evaluate(record):
    claim = Claim(text=record["claim"])
    evidence = [
        Evidence(
            title=e["title"], url=e["url"],
            snippet=e["snippet"], source_score=e["source_score"],
        )
        for e in record["evidence"]
    ]
    return VerdictEngine()._tfidf_evaluate(claim, evidence)


def _score():
    """Return (correct, wrong, abstained, rows) over the whole fixture."""
    correct = wrong = abstained = 0
    rows = []
    for record in _load():
        verdict = _evaluate(record).verdict.value.upper()
        expected = record["expected"]
        if verdict in ABSTAIN:
            outcome, abstained = "abstain", abstained + 1
        elif (expected == "true" and verdict in TRUEISH) or (
            expected == "false" and verdict in FALSEISH
        ):
            outcome, correct = "correct", correct + 1
        else:
            outcome, wrong = "WRONG", wrong + 1
        rows.append((outcome, expected, verdict, record["claim"]))
    return correct, wrong, abstained, rows


@pytest.fixture(scope="module")
def scored():
    return _score()


def test_fixture_is_present_and_substantial():
    records = _load()
    assert len(records) >= 10
    assert sum(len(r["evidence"]) for r in records) >= 100


def test_never_confidently_wrong(scored):
    """
    No claim may be decided in the wrong direction.

    Calling a true claim false, or a false claim true, is the failure this
    product exists to avoid — worse than saying "not enough evidence".
    """
    _, wrong, _, rows = scored
    misses = [r for r in rows if r[0] == "WRONG"]
    assert wrong == 0, "decided in the wrong direction:\n" + "\n".join(
        f"  expected {e}, got {v}: {c}" for _, e, v, c in misses
    )


def test_commits_on_enough_claims(scored):
    """
    Coverage floor. Abstaining everywhere would trivially satisfy the precision
    test above while making the product useless, so the engine must actually
    reach a verdict on a reasonable share of the fixture.

    The floor is set just under the measured baseline (9/12 at the time of
    writing), not at an aspirational number — it exists to catch a regression,
    not to assert the engine is as good as it should be.

    The three it still declines are all false claims whose debunks happen to be
    headlined as questions ("Do We Really Use Only 10 Percent of Our Brain?"),
    which assert nothing and are deliberately withheld from both sides. Getting
    those would mean reading the article body rather than the aggregator
    snippet.
    """
    correct, _, abstained, rows = scored
    total = len(rows)
    assert correct / total >= 0.70, (
        f"only {correct}/{total} claims decided correctly "
        f"({abstained} abstained):\n"
        + "\n".join(f"  [{o:<7}] {v:<12} {c[:60]}" for o, e, v, c in rows)
    )


@pytest.mark.parametrize("expected", ["true", "false"])
def test_both_directions_are_reachable(expected):
    """
    Guard against a one-sided engine. An earlier build could reach FALSE far
    more easily than TRUE — support required a TF-IDF cosine that snippet
    length made unreachable, while refutation only needed a negation word — so
    it read as skeptical of everything, including plain facts.
    """
    decided = 0
    for record in _load():
        if record["expected"] != expected:
            continue
        verdict = _evaluate(record).verdict.value.upper()
        if verdict in (TRUEISH if expected == "true" else FALSEISH):
            decided += 1
    assert decided >= 2, f"engine decided only {decided} '{expected}' claims correctly"
