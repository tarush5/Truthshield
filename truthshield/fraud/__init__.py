"""
Fraud and scam intelligence.

Separate from the fact-checking pipeline in `domain/`, which answers a
different question: that side asks whether a claim is *true* by retrieving
evidence, this side asks whether an artefact is *hostile* by examining its
structure and language. They share the application's infrastructure --
auth, persistence, reporting -- and almost none of their logic.

Every detector returns the same structured finding (`contract.FraudFinding`)
rather than a label, so results from different detectors combine and a score
can always be taken apart into the observations behind it.
"""

from truthshield.fraud import detectors  # noqa: F401  (registers plugins)
from truthshield.fraud.classify import InputKind, classify, extract_entities
from truthshield.fraud.contract import (
    FraudCategory, FraudFinding, Indicator, RiskLevel, Severity,
)
from truthshield.fraud.registry import FraudDetector, analyze, catalogue, register

__all__ = [
    "FraudCategory",
    "FraudDetector",
    "FraudFinding",
    "Indicator",
    "InputKind",
    "RiskLevel",
    "Severity",
    "analyze",
    "catalogue",
    "classify",
    "extract_entities",
    "register",
]
