"""
Central risk engine.

What these pin is the contract the UI relies on: the breakdown sums to the
score, clean families do not dilute a strong one, one keyword cannot reach
the top, the scale never claims certainty, and confidence is its own axis.
"""

import json

import pytest

from truthshield.fraud.contract import Severity
from truthshield.investigations.risk import RiskEngine, band_for
from truthshield.investigations.risk_config import RiskConfig, load_risk_config
from truthshield.investigations.types import (
    EngineKind, EngineResult, EngineStatus, Family, Provenance, Signal,
)


def sig(code, family=Family.NLP, severity=Severity.HIGH, provenance=Provenance.HEURISTIC, confidence=0.7):
    return Signal(code=code, title=code.replace("_", " "), family=family, severity=severity,
                  provenance=provenance, engine="test", engine_version="0", explanation="x",
                  confidence=confidence)


def engines(*statuses):
    return [EngineResult(engine=f"e{i}", version="0", kind=EngineKind.HEURISTIC, status=s)
            for i, s in enumerate(statuses)]


OK2 = engines(EngineStatus.OK, EngineStatus.OK)


class TestScore:
    def test_no_signals_scores_zero_with_capped_confidence(self):
        a = RiskEngine(RiskConfig()).assess([], OK2, {"nlp", "url"})
        assert a.score == 0 and a.level == "LOW"
        assert a.confidence <= 0.35, "absence of signals must not read as confident safety"

    def test_breakdown_sums_exactly_to_the_score(self):
        signals = [sig("a"), sig("b", severity=Severity.MEDIUM), sig("c", Family.URL),
                   sig("d", Family.URL, Severity.LOW), sig("e", Family.EVIDENCE, provenance=Provenance.RETRIEVED)]
        a = RiskEngine(RiskConfig()).assess(signals, OK2, {"nlp", "url", "evidence"})
        assert sum(c.points for c in a.contributions) == a.score
        assert a.score > 0

    def test_a_single_signal_cannot_reach_critical(self):
        a = RiskEngine(RiskConfig()).assess([sig("only")], OK2, {"nlp"})
        assert a.level in ("LOW", "MEDIUM")
        assert a.score <= 45

    def test_clean_families_do_not_dilute_a_strong_one(self):
        strong = [sig("a", Family.URL), sig("b", Family.URL), sig("c", Family.URL)]
        alone = RiskEngine(RiskConfig()).assess(strong, OK2, {"url"})
        with_clean = RiskEngine(RiskConfig()).assess(strong, OK2, {"url", "nlp", "evidence"})
        assert alone.score == with_clean.score

    def test_independent_families_that_agree_compound(self):
        url = [sig("a", Family.URL), sig("b", Family.URL)]
        nlp = [sig("c"), sig("d")]
        one = RiskEngine(RiskConfig()).assess(url, OK2, {"url"})
        both = RiskEngine(RiskConfig()).assess(url + nlp, OK2, {"url", "nlp"})
        assert both.score > one.score

    def test_the_scale_never_claims_certainty(self):
        many = [sig(f"n{i}") for i in range(8)] + [sig(f"u{i}", Family.URL) for i in range(8)]
        a = RiskEngine(RiskConfig()).assess(many, OK2, {"nlp", "url"})
        assert a.score == 99 and a.level == "CRITICAL"

    def test_info_signals_contribute_nothing(self):
        a = RiskEngine(RiskConfig()).assess([sig("note", severity=Severity.INFO)], OK2, {"nlp"})
        assert a.score == 0 and a.contributions == []


class TestConfidence:
    def test_heuristic_only_results_are_capped(self):
        many = [sig(f"n{i}", confidence=1.0) for i in range(5)] + [sig(f"u{i}", Family.URL, confidence=1.0) for i in range(5)]
        a = RiskEngine(RiskConfig()).assess(many, OK2, {"nlp", "url"})
        assert a.confidence <= 0.85

    def test_engines_that_did_not_run_reduce_confidence(self):
        signals = [sig("a"), sig("b", Family.URL)]
        full = RiskEngine(RiskConfig()).assess(signals, OK2, {"nlp", "url"})
        partial = RiskEngine(RiskConfig()).assess(
            signals, engines(EngineStatus.OK, EngineStatus.OK, EngineStatus.UNAVAILABLE), {"nlp", "url"})
        assert partial.confidence < full.confidence
        assert any("Not every applicable engine ran" in n for n in partial.notes)

    @pytest.mark.parametrize("value,band", [(0.9, "HIGH"), (0.6, "MODERATE"), (0.4, "LOW"), (0.1, "VERY_LOW")])
    def test_bands(self, value, band):
        assert band_for(value) == band


class TestConfiguration:
    def test_weights_change_the_score(self):
        signals = [sig("a", Family.URL), sig("b", Family.URL)] + [sig("c"), sig("d")]
        default = RiskEngine(RiskConfig()).assess(signals, OK2, {"nlp", "url"})
        low_url = RiskConfig(weights={**RiskConfig().weights, "url": 2.0}, source="custom")
        tuned = RiskEngine(low_url).assess(signals, OK2, {"nlp", "url"})
        assert tuned.score < default.score
        assert tuned.config["version"] != default.config["version"]

    def test_assessment_records_the_config_it_used(self):
        a = RiskEngine(RiskConfig()).assess([sig("a")], OK2, {"nlp"})
        assert a.config["weights"]["nlp"] == 20 and a.config["version"].startswith("default-")

    def test_invalid_override_falls_back_to_defaults(self, monkeypatch):
        from truthshield.settings import get_settings
        monkeypatch.setattr(get_settings(), "RISK_WEIGHTS_JSON", json.dumps({"weights": {"nonsense": 5}}))
        assert load_risk_config().source == "default"

    def test_valid_override_is_applied(self, monkeypatch):
        from truthshield.settings import get_settings
        monkeypatch.setattr(get_settings(), "RISK_WEIGHTS_JSON",
                            json.dumps({"weights": {"url": 30}, "thresholds": {"critical": 90}}))
        config = load_risk_config()
        assert config.source == "custom" and config.weights["url"] == 30 and config.thresholds["critical"] == 90
