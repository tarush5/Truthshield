"""Abstention: "nothing found" is only a finding when everything that applied ran."""

from truthshield.fraud.contract import Severity
from truthshield.investigations import explain
from truthshield.investigations.risk import RiskEngine
from truthshield.investigations.types import (
    EngineKind, EngineResult, EngineStatus, Family, Provenance, Signal,
)


def engine(name, status=EngineStatus.OK, signals=()):
    return EngineResult(engine=name, version="1", kind=EngineKind.HEURISTIC,
                        status=status, signals=list(signals))


def signal():
    return Signal(code="x", title="X", family=Family.NLP, severity=Severity.HIGH,
                  provenance=Provenance.HEURISTIC, engine="text", engine_version="1",
                  explanation="x")


def assess(*engines):
    return RiskEngine().assess([s for e in engines for s in e.signals], engines, {"nlp"})


def test_everything_ran_and_nothing_fired_is_assessed():
    a = assess(engine("text"), engine("evidence", EngineStatus.NOT_APPLICABLE))
    assert a.determination == "ASSESSED" and a.abstention_reason is None
    assert explain.classify(a, [])[0] == "no_significant_signals"


def test_a_missing_check_with_no_signal_is_inconclusive():
    a = assess(engine("text"), engine("evidence", EngineStatus.UNAVAILABLE))
    assert a.determination == "INCONCLUSIVE"
    assert "evidence" in a.abstention_reason
    label, _ = explain.classify(a, [])
    assert label == "inconclusive"
    assert explain.summarise(a, label).startswith("Inconclusive.")
    assert explain.recommended_actions(label, None)["do_not"] == [
        "Do not read this result as a sign that the content is safe."]


def test_abstention_never_moves_the_score_or_level():
    a = assess(engine("text"), engine("evidence", EngineStatus.ERROR))
    b = assess(engine("text"), engine("evidence", EngineStatus.NOT_APPLICABLE))
    assert (a.score, a.level) == (b.score, b.level)


def test_signals_with_a_missing_check_are_still_assessed():
    a = assess(engine("text", signals=[signal()]), engine("evidence", EngineStatus.UNAVAILABLE))
    assert a.determination == "ASSESSED"
    assert a.score > 0


def test_no_applicable_engine_is_inconclusive():
    a = assess(engine("url", EngineStatus.NOT_APPLICABLE))
    assert a.determination == "INCONCLUSIVE"


def test_a_coverage_gap_with_no_signal_is_inconclusive():
    text = engine("text")
    text.artifacts["coverage_gap"] = "the text is in a language the checks do not cover ('es')"
    a = assess(text)
    assert a.determination == "INCONCLUSIVE" and "'es'" in a.abstention_reason


class TestLanguage:
    def test_hinglish_is_recognised_as_romanized_hindi(self):
        from truthshield.investigations.nlp import detect_language

        r = detect_language("Aapka account block ho gaya hai, turant KYC update karo.")
        assert (r.detected, r.script, r.supported) == ("hi", "latin", True)

    def test_english_is_not_mistaken_for_hinglish(self):
        from truthshield.investigations.nlp import detect_language

        for text in ("Ho ho ho, see you at the main party on Friday.",
                     "Please send the report to the team before the meeting."):
            assert detect_language(text).detected == "en"

    def test_other_indian_scripts_are_named(self):
        from truthshield.investigations.nlp import detect_language

        r = detect_language("আপনার ব্যাংক অ্যাকাউন্ট বন্ধ হয়ে যাবে। এখনই OTP নম্বরটি আমাদের পাঠান।")
        assert (r.detected, r.script, r.supported) == ("bn", "bengali", False)

    def test_unsupported_language_scam_is_inconclusive_not_clean(self, client, auth):
        content = "Su cuenta bancaria será bloqueada hoy. Envíenos el código que recibió ahora mismo."
        r = client.post("/api/v1/investigations", json={"type": "message", "content": content}, headers=auth)
        inv = client.get(f"/api/v1/investigations/{r.json()['id']}", headers=auth).json()
        assert inv["risk_factors"] == []
        assert inv["classification"] == "inconclusive"
        assert inv["result"]["risk"]["determination"] == "INCONCLUSIVE"
