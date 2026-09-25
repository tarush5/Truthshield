"""
The detector plugin system.

A detector declares which input kinds it handles and returns a FraudFinding.
Adding a fraud category means adding one module and registering it -- no
change to the router, the API, the scoring, or anything already working.
That is the whole point of the indirection: the catalogue of fraud types is
open-ended and will keep growing, and a design where each new type touches
the core would decay fast.

Two rules the registry enforces rather than trusting detectors to follow:

**A detector that raises is reported, not swallowed.** The same reasoning as
`detectors/base.py`: a detector that failed and a detector that found
nothing are different answers, and collapsing them tells the reader an input
was cleared when it was never examined.

**Nothing is claimed for a detector that did not run.** The combined result
lists which detectors ran, which declined the input, and which failed, so a
low overall risk score can be read against how much of the system actually
looked at it.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional, Sequence

from truthshield.fraud.classify import Classification, InputKind, classify
from truthshield.fraud.contract import (
    FraudCategory, FraudFinding, Indicator, RiskLevel,
)

logger = logging.getLogger(__name__)


class FraudDetector:
    """Base class for a fraud detection plugin."""

    #: Stable identifier, used in reports and in the registry.
    name: str = "detector"

    #: One line describing what this detector looks for.
    describes: str = ""

    #: Input kinds this detector can say something about.
    handles: Sequence[InputKind] = ()

    def applies_to(self, text: str, classification: Classification) -> bool:
        """Whether this detector has anything to say about this input."""
        return any(classification.has(kind) for kind in self.handles)

    def _run(self, text: str, classification: Classification) -> Optional[FraudFinding]:
        """Do the work. May raise; `analyze` turns that into a reported error."""
        raise NotImplementedError

    def analyze(self, text: str, classification: Classification) -> Optional[FraudFinding]:
        """Run the detector, never raising."""
        try:
            return self._run(text, classification)
        except Exception as exc:
            logger.warning("Fraud detector %s failed: %s", self.name, exc, exc_info=True)
            return FraudFinding(
                detector=self.name,
                category=FraudCategory.UNKNOWN,
                risk_score=0.0,
                confidence=0.0,
                summary="This check could not run.",
                limitations=[f"{self.name} failed: {type(exc).__name__}"],
                methods=[],
            )


_REGISTRY: Dict[str, FraudDetector] = {}


def register(detector: FraudDetector) -> FraudDetector:
    """Add a detector to the registry. Idempotent per name."""
    _REGISTRY[detector.name] = detector
    return detector


def registered() -> List[FraudDetector]:
    return list(_REGISTRY.values())


def catalogue() -> List[dict]:
    """What this deployment can detect, for the API and the UI."""
    return [
        {
            "name": d.name,
            "describes": d.describes,
            "handles": [k.value for k in d.handles],
        }
        for d in sorted(_REGISTRY.values(), key=lambda d: d.name)
    ]


def _combine(findings: List[FraudFinding]) -> tuple:
    """
    One overall risk figure from several detectors.

    Deliberately *not* an average. Averaging lets a confident phishing
    finding be diluted by three detectors that found nothing, which is how a
    real signal disappears into a clean-looking score. The worst finding
    leads, and corroboration from other detectors raises it a little -- two
    detectors independently flagging the same input is stronger evidence
    than either alone.
    """
    usable = [f for f in findings if f.confidence > 0 and f.risk_score > 0]
    if not usable:
        return 0.0, 0.0, FraudCategory.NONE

    usable.sort(key=lambda f: -f.risk_score)
    lead = usable[0]

    corroboration = sum(
        min(6.0, f.risk_score * 0.10) for f in usable[1:]
    )
    score = min(100.0, lead.risk_score + corroboration)

    # Confidence is the lead detector's, nudged up when others agree and
    # never above its own ceiling by much -- agreement between two weak
    # signals is still weak.
    agreement = min(0.15, 0.05 * len(usable[1:]))
    confidence = min(1.0, lead.confidence + agreement)

    return score, confidence, lead.category


def analyze(text: str, *, hint: str = "", only: Optional[Sequence[str]] = None) -> dict:
    """
    Run every applicable detector and combine the results.

    `only` restricts to named detectors, which is what the dedicated
    scanners in the UI use -- a URL scanner should not report on the message
    wrapped around the URL.
    """
    classification = classify(text, hint=hint)

    ran: List[FraudFinding] = []
    skipped: List[str] = []
    failed: List[str] = []

    for detector in _REGISTRY.values():
        if only and detector.name not in only:
            continue
        if not detector.applies_to(text, classification):
            skipped.append(detector.name)
            continue

        finding = detector.analyze(text, classification)
        if finding is None:
            skipped.append(detector.name)
            continue
        if finding.confidence == 0.0 and finding.limitations:
            failed.append(detector.name)
        ran.append(finding)

    score, confidence, category = _combine(ran)

    return {
        "risk_score": round(score, 1),
        "risk_level": RiskLevel.for_score(score).value,
        "confidence": round(confidence, 2),
        "category": category.value,
        "classification": classification.as_dict(),
        "findings": [f.as_dict() for f in ran],
        # How much of the system actually looked. A low score from one
        # detector is a different statement from a low score from six.
        "coverage": {
            "ran": [f.detector for f in ran],
            "not_applicable": skipped,
            "failed": failed,
        },
    }


__all__ = [
    "FraudCategory",
    "FraudDetector",
    "FraudFinding",
    "Indicator",
    "InputKind",
    "RiskLevel",
    "analyze",
    "catalogue",
    "register",
    "registered",
]
