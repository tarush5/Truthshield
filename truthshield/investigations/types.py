"""
The vocabulary every investigation engine speaks.

Pure data, no I/O. The central rule encoded here is that nothing an engine
reports is anonymous: every signal says which engine produced it, at which
version, from what excerpt of the input, and *how* it is known -- a rule, a
trained model, a retrieved source, or a language model's interpretation.
Those are different grades of knowledge and the reader is entitled to see
which one they are looking at.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from truthshield.fraud.contract import SEVERITY_WEIGHT, Severity


class InvestigationType(str, Enum):
    TEXT = "text"
    URL = "url"
    MESSAGE = "message"
    EMAIL = "email"


class InvestigationStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    ANALYZING = "ANALYZING"
    COLLECTING_EVIDENCE = "COLLECTING_EVIDENCE"
    CALCULATING_RISK = "CALCULATING_RISK"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

    @property
    def is_terminal(self) -> bool:
        return self in (InvestigationStatus.COMPLETED, InvestigationStatus.FAILED)


class Stage(str, Enum):
    """The universal pipeline, in order. Every one is recorded, even when skipped."""

    VALIDATION = "VALIDATION"
    HASHING = "HASHING"
    EXTRACTION = "EXTRACTION"
    CLASSIFICATION = "CLASSIFICATION"
    FEATURE_EXTRACTION = "FEATURE_EXTRACTION"
    MODEL_ANALYSIS = "MODEL_ANALYSIS"
    EVIDENCE_RETRIEVAL = "EVIDENCE_RETRIEVAL"
    CROSS_MODAL_ANALYSIS = "CROSS_MODAL_ANALYSIS"
    RISK_ENGINE = "RISK_ENGINE"
    EXPLANATION = "EXPLANATION"
    REPORT = "REPORT"
    STORAGE = "STORAGE"


# Which status the investigation shows while a stage is running.
STAGE_STATUS: Dict[Stage, InvestigationStatus] = {
    Stage.VALIDATION: InvestigationStatus.PROCESSING,
    Stage.HASHING: InvestigationStatus.PROCESSING,
    Stage.EXTRACTION: InvestigationStatus.PROCESSING,
    Stage.CLASSIFICATION: InvestigationStatus.PROCESSING,
    Stage.FEATURE_EXTRACTION: InvestigationStatus.ANALYZING,
    Stage.MODEL_ANALYSIS: InvestigationStatus.ANALYZING,
    Stage.EVIDENCE_RETRIEVAL: InvestigationStatus.COLLECTING_EVIDENCE,
    Stage.CROSS_MODAL_ANALYSIS: InvestigationStatus.ANALYZING,
    Stage.RISK_ENGINE: InvestigationStatus.CALCULATING_RISK,
    Stage.EXPLANATION: InvestigationStatus.CALCULATING_RISK,
    Stage.REPORT: InvestigationStatus.CALCULATING_RISK,
    Stage.STORAGE: InvestigationStatus.CALCULATING_RISK,
}


class Family(str, Enum):
    """Signal families -- the unit the risk engine weights."""

    NLP = "nlp"
    URL = "url"
    REPUTATION = "reputation"
    BEHAVIORAL = "behavioral"
    DOCUMENT_MEDIA = "document_media"
    EVIDENCE = "evidence"


class Provenance(str, Enum):
    """How a signal is known. Shown on every signal in the UI."""

    HEURISTIC = "heuristic"
    ML_PREDICTION = "ml_prediction"
    RETRIEVED = "retrieved"
    LLM = "llm"


class EngineKind(str, Enum):
    HEURISTIC = "heuristic"
    ML = "ml"
    RETRIEVAL = "retrieval"
    LLM = "llm"


class EngineStatus(str, Enum):
    OK = "ok"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    NOT_APPLICABLE = "not_applicable"


class Signal(BaseModel):
    code: str
    title: str
    family: Family
    severity: Severity
    provenance: Provenance
    engine: str
    engine_version: str
    explanation: str
    evidence: Optional[str] = None       # verbatim excerpt that triggered it
    confidence: float = 0.6
    weight: float = 1.0

    @property
    def contribution(self) -> float:
        """Raw pull on the family score, before decay -- same scale as 1.x Indicators."""
        return SEVERITY_WEIGHT[self.severity] * self.weight


class ModelPredictionRecord(BaseModel):
    # `model_*` field names are the spec's vocabulary; pydantic reserves the
    # prefix only for its own methods, none of which these collide with.
    model_config = {"protected_namespaces": ()}

    model_name: str
    model_version: str
    model_kind: EngineKind
    task: str
    input_sha256: str
    prediction: Dict[str, Any] = Field(default_factory=dict)
    confidence: Optional[float] = None


class EngineResult(BaseModel):
    engine: str
    version: str
    kind: EngineKind
    status: EngineStatus = EngineStatus.OK
    signals: List[Signal] = Field(default_factory=list)
    features: Dict[str, Any] = Field(default_factory=dict)
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    predictions: List[ModelPredictionRecord] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    duration_ms: int = 0
    detail: Optional[str] = None

    @property
    def ran(self) -> bool:
        return self.status is EngineStatus.OK

    def summary(self) -> dict:
        return {
            "name": self.engine,
            "version": self.version,
            "kind": self.kind.value,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
            "signals": len(self.signals),
            "limitations": self.limitations,
            "detail": self.detail,
        }


class InvestigationContext(BaseModel):
    """Everything an engine may read. Engines add to `artifacts`, never to input."""

    investigation_id: str
    type: InvestigationType
    content: str                     # original, as submitted
    normalized: str = ""             # filled by the text engine
    input_sha256: str
    language_hint: str = "auto"
    # Demo samples use invented domains that someone may since have
    # registered; the platform must not visit them on a demo's behalf.
    allow_page_fetch: bool = True
    urls: List[str] = Field(default_factory=list)
    artifacts: Dict[str, Any] = Field(default_factory=dict)
