"""
What every fraud detector must return.

The governing rule is that a finding is never just "fraud" or "not fraud".
A bare label is unusable: the reader cannot tell whether to act on it, cannot
see what triggered it, and cannot tell a strong signal from a weak one. So
every detector returns the same structured finding, and the fields that make
it auditable are required rather than optional.

Three of those fields exist specifically to stop this system overclaiming:

  `indicators`   what was actually observed, each with its own weight, so a
                 score can be taken apart rather than trusted whole.
  `limitations`  what the detector could not check. A phishing verdict
                 reached without domain-reputation data is a different
                 finding from one reached with it, and the reader is
                 entitled to know which they have.
  `confidence`   separate from risk. High risk at low confidence means
                 "this looks bad and I am not sure", which is a real and
                 common state that a single number cannot express.

Risk and confidence are deliberately two axes. Collapsing them is how a
detector ends up saying 90/100 CRITICAL on the strength of one keyword.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class RiskLevel(str, Enum):
    """
    Bands over the 0-100 score.

    Named rather than numeric at the presentation layer because "68" means
    nothing to a reader deciding whether to click a link.
    """

    SAFE = "SAFE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @classmethod
    def for_score(cls, score: float) -> "RiskLevel":
        if score >= 85:
            return cls.CRITICAL
        if score >= 65:
            return cls.HIGH
        if score >= 40:
            return cls.MEDIUM
        if score >= 15:
            return cls.LOW
        return cls.SAFE


class FraudCategory(str, Enum):
    """
    What kind of fraud this looks like.

    Open-ended by design -- new detectors add members rather than reusing a
    near-miss, because a wrong category sends the reader to the wrong
    safety advice, which is worse than no category.
    """

    UNKNOWN = "UNKNOWN"
    NONE = "NONE"                        # examined, nothing found

    PHISHING = "PHISHING"
    SMISHING = "SMISHING"                # phishing over SMS
    BANK_IMPERSONATION = "BANK_IMPERSONATION"
    GOVERNMENT_IMPERSONATION = "GOVERNMENT_IMPERSONATION"
    PAYMENT_SCAM = "PAYMENT_SCAM"
    ADVANCE_FEE = "ADVANCE_FEE"
    LOTTERY_PRIZE = "LOTTERY_PRIZE"
    JOB_SCAM = "JOB_SCAM"
    LOAN_SCAM = "LOAN_SCAM"
    INVESTMENT_SCAM = "INVESTMENT_SCAM"
    CRYPTO_SCAM = "CRYPTO_SCAM"
    DELIVERY_SCAM = "DELIVERY_SCAM"
    TECH_SUPPORT = "TECH_SUPPORT"
    ECOMMERCE_SCAM = "ECOMMERCE_SCAM"
    ROMANCE_SCAM = "ROMANCE_SCAM"
    SOCIAL_ENGINEERING = "SOCIAL_ENGINEERING"
    MALWARE_DELIVERY = "MALWARE_DELIVERY"


class Severity(str, Enum):
    """How much a single indicator should move the score."""

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


# What each severity contributes before weighting. Kept here rather than in
# each detector so two detectors cannot disagree about what "HIGH" means.
SEVERITY_WEIGHT: Dict[Severity, float] = {
    Severity.INFO: 0.0,
    Severity.LOW: 0.25,
    Severity.MEDIUM: 0.55,
    Severity.HIGH: 1.0,
}


@dataclass(frozen=True)
class Indicator:
    """
    One observation, and what it is worth.

    `evidence` is the literal thing seen -- the matched substring, the
    decoded hostname, the header value. Without it the reader has a claim
    and no way to check it, which is the failure mode this whole contract
    is arranged against.
    """

    code: str                    # stable identifier, e.g. "punycode_host"
    title: str                   # human-readable, e.g. "Disguised domain"
    severity: Severity
    explanation: str             # why this matters, in plain language
    evidence: Optional[str] = None
    weight: float = 1.0          # detector-specific multiplier

    @property
    def contribution(self) -> float:
        return SEVERITY_WEIGHT[self.severity] * self.weight

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "title": self.title,
            "severity": self.severity.value,
            "explanation": self.explanation,
            "evidence": self.evidence,
            "contribution": round(self.contribution, 3),
        }


@dataclass
class FraudFinding:
    """
    One detector's complete answer.

    Carries its own identity and timestamp so a finding can be cited in a
    support conversation or a case file without needing the request that
    produced it.
    """

    detector: str
    category: FraudCategory
    risk_score: float                          # 0-100
    confidence: float                          # 0-1, how sure the detector is
    summary: str                               # one line, plain language
    indicators: List[Indicator] = field(default_factory=list)
    recommended_action: str = ""
    limitations: List[str] = field(default_factory=list)
    methods: List[str] = field(default_factory=list)   # rules/ml/intel used
    analysis_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Clamped rather than trusted. A detector doing its own arithmetic
        # can overshoot, and a 130/100 score in a report destroys confidence
        # in every other number beside it.
        self.risk_score = max(0.0, min(100.0, float(self.risk_score)))
        self.confidence = max(0.0, min(1.0, float(self.confidence)))

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.for_score(self.risk_score)

    def as_dict(self) -> dict:
        return {
            "analysis_id": self.analysis_id,
            "detector": self.detector,
            "category": self.category.value,
            "risk_score": round(self.risk_score, 1),
            "risk_level": self.risk_level.value,
            "confidence": round(self.confidence, 2),
            "summary": self.summary,
            "indicators": [i.as_dict() for i in self.indicators],
            "recommended_action": self.recommended_action,
            # Always present, never omitted when empty: an absent key reads
            # as "nothing was missed", and that is a claim of its own.
            "limitations": self.limitations,
            "methods": self.methods,
            "detected_at": self.detected_at.isoformat(),
            **({"extra": self.extra} if self.extra else {}),
        }


def score_from_indicators(
    indicators: List[Indicator],
    *,
    ceiling: float = 100.0,
    single_indicator_cap: float = 45.0,
) -> float:
    """
    Combine indicators into a 0-100 score.

    Two properties, both learned the hard way on the text fraud detector
    earlier in this codebase:

    **One indicator cannot reach the top.** A single saturated signal
    previously scored ordinary pushy marketing above a conspiracy sample.
    Breadth is what separates a scam from a pushy sentence, so a lone
    indicator is capped well below CRITICAL however severe it is.

    **Additional indicators have diminishing returns.** Ten instances of
    the same tactic is not ten times the evidence, so contributions are
    summed with a decay rather than linearly.
    """
    if not indicators:
        return 0.0

    ranked = sorted(indicators, key=lambda i: -i.contribution)

    total = 0.0
    for position, indicator in enumerate(ranked):
        # 1.0, 0.72, 0.52, 0.37 ... the fifth corroborating signal matters
        # much less than the second.
        decay = 0.72 ** position
        total += indicator.contribution * decay

    # Normalised against a notional "three strong indicators" ceiling.
    score = min(ceiling, (total / 2.2) * 100.0)

    if len(indicators) == 1:
        score = min(score, single_indicator_cap)

    return round(score, 1)
