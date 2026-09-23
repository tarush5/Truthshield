"""
Request and response shapes.

Separate from the domain types on purpose: the wire format is a contract with
the frontend and can stay stable while the domain evolves. Responses expose
the reasoning — components, limitations, per-source stance — because a verdict
the reader cannot interrogate is not much use in a fact-checking tool.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from truthshield.domain.types import (
    AnalysisReport, ConfidenceBand, ContentType, Language, Stance, Verdict,
)


# ── Auth ──────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=256)

    @field_validator("password")
    @classmethod
    def _not_trivial(cls, v: str) -> str:
        # A 6-character minimum was the previous rule, which permits a
        # password a commodity GPU exhausts in seconds.
        if v.isdigit() or v.isalpha():
            raise ValueError("Password must mix letters with numbers or symbols.")
        return v


class SigninRequest(BaseModel):
    email: EmailStr
    password: str


class OTPRequest(BaseModel):
    email: EmailStr


class OTPVerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserSummary"


class UserSummary(BaseModel):
    id: str
    email: str
    org_id: Optional[str] = None


# ── Analysis ──────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    text: Optional[str] = None
    url: Optional[str] = None
    language: Language = Language.EN
    async_mode: bool = False

    @field_validator("text")
    @classmethod
    def _text_not_blank(cls, v):
        return v.strip() if v and v.strip() else None


class EvidenceOut(BaseModel):
    title: str
    url: str
    snippet: str
    source_score: float
    source_domain: Optional[str]
    stance: Stance

    # The reader should be able to see why a source was weighted as it was.
    credibility_label: str

    @classmethod
    def of(cls, item) -> "EvidenceOut":
        score = item.source_score
        if score >= 0.90:
            label = "Authoritative"
        elif score >= 0.70:
            label = "Reliable"
        elif score >= 0.50:
            label = "Mixed"
        elif score > 0:
            label = "Low quality"
        else:
            label = "Known disinformation"
        return cls(
            title=item.title, url=item.url, snippet=item.snippet,
            source_score=item.source_score, source_domain=item.source_domain,
            stance=item.stance, credibility_label=label,
        )


class ClaimOut(BaseModel):
    text: str
    verdict: Verdict
    confidence: float
    reasoning: str
    evidence: List[EvidenceOut]
    supporting_count: int
    refuting_count: int

    @classmethod
    def of(cls, cv) -> "ClaimOut":
        return cls(
            text=cv.claim.text,
            verdict=cv.verdict,
            confidence=round(cv.confidence, 3),
            reasoning=cv.reasoning,
            evidence=[EvidenceOut.of(e) for e in cv.evidence],
            supporting_count=len(cv.supporting),
            refuting_count=len(cv.refuting),
        )


class DetectorOut(BaseModel):
    name: str
    status: str
    score: float
    method: str
    detail: Optional[str]
    # Explicit, so the UI never renders an unavailable detector as a pass.
    counted_toward_score: bool


class ReportOut(BaseModel):
    id: str
    status: str = "complete"
    content_type: ContentType
    language: Language
    original_text: Optional[str]
    source_url: Optional[str]

    verdict: Verdict
    trust_score: int
    fake_probability: int
    confidence_band: ConfidenceBand
    breakdown: Dict[str, float]

    summary: str
    reasons: List[str]
    limitations: List[str]

    claims: List[ClaimOut]
    detectors: List[DetectorOut]

    # Retrieval-augmented, and both empty unless configured. Always present
    # in the response rather than conditionally included, so a client renders
    # an absence instead of branching on a missing key.
    prior_claims: List[Dict[str, Any]] = []
    explanation: Optional[Dict[str, Any]] = None

    processing_time_seconds: float
    created_at: datetime

    @classmethod
    def of(cls, report: AnalysisReport, status: str = "complete") -> "ReportOut":
        return cls(
            id=report.id,
            status=status,
            content_type=report.content_type,
            language=report.language,
            original_text=report.original_text,
            source_url=report.source_url,
            verdict=report.verdict,
            trust_score=report.trust_score,
            fake_probability=report.fake_probability,
            confidence_band=report.confidence_band,
            breakdown=report.breakdown.model_dump(),
            summary=report.summary,
            reasons=report.reasons,
            limitations=report.limitations,
            claims=[ClaimOut.of(c) for c in report.claims],
            detectors=[
                DetectorOut(
                    name=d.name, status=d.status.value, score=d.score,
                    method=d.method, detail=d.detail,
                    counted_toward_score=d.counts_toward_scoring,
                )
                for d in report.detectors
            ],
            prior_claims=report.prior_claims,
            explanation=report.explanation,
            processing_time_seconds=report.processing_time_seconds,
            created_at=report.created_at,
        )


class SharedReportOut(BaseModel):
    """
    A report as a stranger holding the link sees it.

    Deliberately narrower than `ReportOut`. It carries the finding and the
    evidence behind it, and drops everything that identifies the account
    that ran it -- including the report id, which would otherwise let a
    holder of a public link go probing the authenticated routes with it.
    """

    content_type: ContentType
    language: Language
    original_text: Optional[str]
    source_url: Optional[str]

    verdict: Verdict
    trust_score: int
    fake_probability: int
    confidence_band: ConfidenceBand
    breakdown: Dict[str, float]

    summary: str
    reasons: List[str]
    limitations: List[str]

    claims: List[ClaimOut]
    detectors: List[DetectorOut]
    explanation: Optional[Dict[str, Any]] = None

    created_at: datetime
    shared_at: Optional[datetime] = None

    @classmethod
    def of(cls, report: AnalysisReport, *, shared_at=None) -> "SharedReportOut":
        return cls(
            content_type=report.content_type,
            language=report.language,
            original_text=report.original_text,
            source_url=report.source_url,
            verdict=report.verdict,
            trust_score=report.trust_score,
            fake_probability=report.fake_probability,
            confidence_band=report.confidence_band,
            breakdown=report.breakdown.model_dump(),
            summary=report.summary,
            reasons=report.reasons,
            limitations=report.limitations,
            claims=[ClaimOut.of(c) for c in report.claims],
            detectors=[
                DetectorOut(
                    name=d.name, status=d.status.value, score=d.score,
                    method=d.method, detail=d.detail,
                    counted_toward_score=d.counts_toward_scoring,
                )
                for d in report.detectors
            ],
            explanation=report.explanation,
            created_at=report.created_at,
            shared_at=shared_at,
        )


class QueuedResponse(BaseModel):
    id: str
    status: str = "queued"
    poll_url: str


class ReportSummary(BaseModel):
    id: str
    status: str
    verdict: Verdict
    trust_score: int
    content_type: ContentType
    excerpt: Optional[str]
    created_at: datetime


class FeedbackRequest(BaseModel):
    report_id: str
    user_verdict: Verdict
    comment: Optional[str] = Field(default=None, max_length=2000)


class StatsResponse(BaseModel):
    total_analyses: int
    verdicts: Dict[str, int]
    average_trust_score: float
    languages: Dict[str, int]


class HealthResponse(BaseModel):
    status: str
    version: str
    database: bool
    cache: Dict[str, Any]
    broker: bool
    capabilities: Dict[str, Any]


TokenResponse.model_rebuild()
