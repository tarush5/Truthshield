"""
Domain types.

Pure data and enums — no I/O, no framework. The API schemas are derived from
these rather than the other way round, so the analysis logic can be tested and
reasoned about without a request in flight.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ContentType(str, Enum):
    TEXT = "text"
    URL = "url"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"


class Language(str, Enum):
    EN = "en"
    HI = "hi"
    TA = "ta"


class Verdict(str, Enum):
    """
    The full verdict vocabulary, ordered from most credible to least.

    INSUFFICIENT_EVIDENCE is a first-class outcome, not a failure mode. A
    fact-checker that must always commit will confidently mislabel whatever it
    could not establish, which is the worse error for this product.
    """

    VERIFIED = "VERIFIED"
    LIKELY_TRUE = "LIKELY TRUE"
    PARTIALLY_TRUE = "PARTIALLY TRUE"
    MIXED_EVIDENCE = "MIXED EVIDENCE"
    MISLEADING = "MISLEADING"
    LIKELY_FALSE = "LIKELY FALSE"
    FALSE = "FALSE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT EVIDENCE"

    @property
    def is_decided(self) -> bool:
        return self not in (Verdict.INSUFFICIENT_EVIDENCE, Verdict.MIXED_EVIDENCE)

    @property
    def leans_true(self) -> bool:
        return self in (Verdict.VERIFIED, Verdict.LIKELY_TRUE, Verdict.PARTIALLY_TRUE)

    @property
    def leans_false(self) -> bool:
        return self in (Verdict.FALSE, Verdict.LIKELY_FALSE, Verdict.MISLEADING)


class Stance(str, Enum):
    SUPPORTS = "SUPPORTS"
    REFUTES = "REFUTES"
    NEUTRAL = "NEUTRAL"
    OFF_TOPIC = "OFF_TOPIC"


class ConfidenceBand(str, Enum):
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    VERY_LOW = "VERY_LOW"


class DetectorStatus(str, Enum):
    """
    Whether a detector actually ran.

    The previous system had no way to express this, so a detector whose model
    failed to load returned confidence 0.0 — indistinguishable from "inspected
    it, found nothing wrong". An image whose OCR, captioning and deepfake model
    had all failed was reported as VERIFIED at 85% trust. UNAVAILABLE exists so
    a result that was never computed cannot be read as a clean bill of health.
    """

    OK = "ok"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    NOT_APPLICABLE = "not_applicable"


class DetectorResult(BaseModel):
    """One detector's output, always carrying whether it ran."""

    name: str
    status: DetectorStatus = DetectorStatus.UNAVAILABLE
    score: float = 0.0              # 0 = benign, 1 = strongly manipulated
    method: str = ""
    detail: Optional[str] = None

    @property
    def ran(self) -> bool:
        return self.status is DetectorStatus.OK

    @property
    def counts_toward_scoring(self) -> bool:
        """Only a detector that ran may influence the trust score."""
        return self.ran


class Claim(BaseModel):
    text: str
    entity: Optional[str] = None
    date: Optional[str] = None
    location: Optional[str] = None


class EvidenceItem(BaseModel):
    title: str
    url: str
    snippet: str = ""
    source_score: float = 0.5
    stance: Stance = Stance.NEUTRAL

    # The publisher's own domain, when `url` does not identify them.
    # Aggregators such as Google News return interstitial links; scoring those
    # rated every article as an aggregator regardless of who reported it.
    source_domain: Optional[str] = None

    @property
    def scoring_domain(self) -> str:
        return self.source_domain or self.url


class ClaimVerdict(BaseModel):
    claim: Claim
    verdict: Verdict = Verdict.INSUFFICIENT_EVIDENCE
    confidence: float = 0.0
    reasoning: str = ""
    evidence: List[EvidenceItem] = Field(default_factory=list)

    @property
    def supporting(self) -> List[EvidenceItem]:
        return [e for e in self.evidence if e.stance is Stance.SUPPORTS]

    @property
    def refuting(self) -> List[EvidenceItem]:
        return [e for e in self.evidence if e.stance is Stance.REFUTES]


class ContentPacket(BaseModel):
    """Normalized input, whatever the original medium."""

    content_type: ContentType
    language: Language = Language.EN
    text: Optional[str] = None
    source_url: Optional[str] = None
    file_path: Optional[str] = None
    frame_paths: List[str] = Field(default_factory=list)
    audio_path: Optional[str] = None
    metadata: Dict[str, str] = Field(default_factory=dict)

    @property
    def has_text(self) -> bool:
        return bool(self.text and self.text.strip())


class TrustBreakdown(BaseModel):
    """The components behind a trust score, exposed so it can be challenged."""

    fact_match: float = 50.0
    source_credibility: float = 50.0
    evidence_strength: float = 50.0
    manipulation_risk: float = 50.0


class AnalysisReport(BaseModel):
    id: str
    content_type: ContentType
    language: Language = Language.EN
    original_text: Optional[str] = None
    source_url: Optional[str] = None

    verdict: Verdict = Verdict.INSUFFICIENT_EVIDENCE
    trust_score: int = 50
    confidence_band: ConfidenceBand = ConfidenceBand.MODERATE
    breakdown: TrustBreakdown = Field(default_factory=TrustBreakdown)

    claims: List[ClaimVerdict] = Field(default_factory=list)
    detectors: List[DetectorResult] = Field(default_factory=list)

    summary: str = ""
    reasons: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)

    processing_time_seconds: float = 0.0
    created_at: datetime = Field(default_factory=_utcnow)

    @property
    def fake_probability(self) -> int:
        """
        Likelihood the content is misinformation, stated outright.

        Not a plain inversion of trust: a low-confidence assessment is pulled
        toward 50, so "we could not establish much" never reads as a confident
        accusation.
        """
        shrink = {
            ConfidenceBand.HIGH: 1.0,
            ConfidenceBand.MODERATE: 0.85,
            ConfidenceBand.LOW: 0.65,
            ConfidenceBand.VERY_LOW: 0.45,
        }[self.confidence_band]
        raw = 100 - self.trust_score
        return max(0, min(100, round(50 + (raw - 50) * shrink)))
