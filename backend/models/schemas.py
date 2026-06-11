"""
TruthShield — Pydantic Schemas
All request/response models for the API and internal data flow.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


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
