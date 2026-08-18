"""
TruthShield — Pydantic Schemas
All request/response models for the API and internal data flow.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl, model_validator


def _fake_label(p: int) -> str:
    """
    Plain-language band for a misinformation likelihood (0-100).

    Cut points mirror the trust-score bands the verdict uses (the aggregator
    clamps LIKELY FALSE to 15-44 trust, i.e. 56-85 fake), so the label and the
    verdict never disagree in front of the user — a "LIKELY FALSE" verdict
    reading "UNCERTAIN" next to it undermines both.
    """
    if p >= 75:
        return "VERY LIKELY FAKE"
    if p >= 56:
        return "LIKELY FAKE"
    if p > 44:
        return "UNCERTAIN"
    if p > 25:
        return "LIKELY GENUINE"
    return "VERY LIKELY GENUINE"


# ═══════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════

class ContentType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    URL = "url"


class Verdict(str, Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    MISLEADING = "MISLEADING"
    UNVERIFIED = "UNVERIFIED"


class Language(str, Enum):
    EN = "en"
    HI = "hi"
    TA = "ta"


# ═══════════════════════════════════════════════
# Core Data Packets
# ═══════════════════════════════════════════════

class ContentPacket(BaseModel):
    """Standardized output from the preprocessor."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    content_type: ContentType
    text: Optional[str] = None
    lang: Language = Language.EN
    embeddings: Optional[List[float]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    image_paths: List[str] = Field(default_factory=list)
    audio_path: Optional[str] = None
    video_path: Optional[str] = None
    source_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════
# Detector Outputs
# ═══════════════════════════════════════════════

class TextClassificationResult(BaseModel):
    label: str = "unknown"  # fake / real / misleading
    confidence: float = 0.0
    explanation_tokens: List[str] = Field(default_factory=list)


class DeepfakeResult(BaseModel):
    is_deepfake: bool = False
    confidence: float = 0.0
    flagged_frames: List[int] = Field(default_factory=list)
    needs_human_review: bool = False


class VoiceCloneResult(BaseModel):
    is_cloned: bool = False
    confidence: float = 0.0
    anomaly_score: float = 0.0


class AIContentResult(BaseModel):
    ai_generated_probability: float = 0.0
    method: str = "perplexity_scoring"
    explanation: Optional[str] = None


class SocialSignal(BaseModel):
    platform: str
    virality_score: float = 0.0
    engagement: Dict[str, int] = Field(default_factory=dict)
    flagged_by_users: int = 0


class CredibilityScore(BaseModel):
    trust_score: int = 50  # 0–100
    verdict: str = "UNVERIFIED"
    component_scores: Dict[str, float] = Field(default_factory=dict)
    confidence_band: str = "MODERATE"  # HIGH / MODERATE / LOW / VERY_LOW

    # Explicit likelihood that the content is misinformation, 0–100.
    # trust_score answers "how far can this be relied on"; readers generally
    # want the inverse stated outright rather than inferred from 100 - trust.
    # Deliberately not a plain inversion: a low-confidence assessment is pulled
    # toward 50 so an uncertain result cannot read as a confident accusation.
    fake_probability: int = 50
    fake_likelihood_label: str = "UNCERTAIN"  # VERY LIKELY FAKE … VERY LIKELY GENUINE

    @model_validator(mode="after")
    def _derive_fake_probability(self):
        """
        Derive the misinformation likelihood from trust and confidence.

        Computed here rather than at each call site so every construction path
        (full pipeline, degraded fallback, standalone scorer) reports the same
        number instead of some of them silently keeping the 50 default.

        Confidence shrinks the result toward 50: at VERY_LOW confidence a trust
        score of 20 means "we could not establish much", not "80% fake".
        """
        raw = 100 - int(self.trust_score)
        shrink = {
            "HIGH": 1.0,
            "MODERATE": 0.85,
            "LOW": 0.65,
            "VERY_LOW": 0.45,
        }.get((self.confidence_band or "MODERATE").upper(), 0.85)

        self.fake_probability = max(0, min(100, int(round(50 + (raw - 50) * shrink))))
        self.fake_likelihood_label = _fake_label(self.fake_probability)
        return self


# ═══════════════════════════════════════════════
# Fact-Check Models
# ═══════════════════════════════════════════════

class Claim(BaseModel):
    text: str
    entity: Optional[str] = None
    date: Optional[str] = None
    location: Optional[str] = None


class Evidence(BaseModel):
    title: str
    url: str
    snippet: str
    source_score: float = 0.5
    stance: str = "NEUTRAL"


class ClaimVerdict(BaseModel):
    claim: Claim
    verdict: Verdict = Verdict.UNVERIFIED
    reasoning: str = ""
    confidence: float = 0.0
    evidence: List[Evidence] = Field(default_factory=list)


# ═══════════════════════════════════════════════
# Counter-Response Models
# ═══════════════════════════════════════════════

class Inconsistency(BaseModel):
    span_start: int = 0
    span_end: int = 0
    reason: str = ""
    severity: str = "medium"  # low / medium / high


class CounterNarrative(BaseModel):
    summary_en: str = ""
    summary_hi: str = ""
    summary_ta: str = ""
    sources_cited: List[str] = Field(default_factory=list)


class Explanation(BaseModel):
    text_en: str = ""
    text_hi: str = ""
    text_ta: str = ""


# ═══════════════════════════════════════════════
# API Request / Response
# ═══════════════════════════════════════════════

class AnalyzeRequest(BaseModel):
    url: Optional[str] = None
    text: Optional[str] = None
    lang: Language = Language.EN


class AnalysisReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    content_type: ContentType = ContentType.TEXT
    original_text: Optional[str] = None
    language: Language = Language.EN
    credibility: CredibilityScore = Field(default_factory=CredibilityScore)
    text_classification: Optional[TextClassificationResult] = None
    deepfake_result: Optional[DeepfakeResult] = None
    voice_clone_result: Optional[VoiceCloneResult] = None
    ai_content_result: Optional[AIContentResult] = None
    social_signals: List[SocialSignal] = Field(default_factory=list)
    claims: List[ClaimVerdict] = Field(default_factory=list)
    inconsistencies: List[Inconsistency] = Field(default_factory=list)
    counter_narrative: Optional[CounterNarrative] = None
    explanation: Optional[Explanation] = None
    source_url: Optional[str] = None
    is_crisis_content: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    processing_time_seconds: float = 0.0
    # Pipeline telemetry & aggregation fields
    pipeline_stages: List[Dict[str, Any]] = Field(default_factory=list)
    signal_correlations: Dict[str, float] = Field(default_factory=dict)
    risk_factors: List[str] = Field(default_factory=list)
    confidence_profile: Optional[Dict[str, Any]] = None
    verdict_reasons: List[str] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    report_id: str
    user_verdict: Verdict
    comment: Optional[str] = None


class StatsResponse(BaseModel):
    total_analyses: int = 0
    verdicts: Dict[str, int] = Field(default_factory=dict)
    language_distribution: Dict[str, int] = Field(default_factory=dict)
    top_flagged_domains: List[Dict[str, Any]] = Field(default_factory=list)
    avg_trust_score: float = 50.0


class WSProgressMessage(BaseModel):
    stage: str  # preprocessing / detecting / verifying / explaining / done
    progress: float  # 0.0–1.0
    message: str = ""
    partial_result: Optional[Dict[str, Any]] = None
