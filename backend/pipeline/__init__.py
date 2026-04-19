"""
TruthShield — Pipeline Package
Structured decision pipeline with result aggregation and confidence scoring.
"""

from backend.pipeline.decision_pipeline import DecisionPipeline, PipelineContext, PipelineStage
from backend.pipeline.result_aggregator import ResultAggregator, AggregatedResult
from backend.pipeline.confidence_scorer import ConfidenceScorer as PipelineConfidenceScorer, ConfidenceProfile

__all__ = [
    "DecisionPipeline",
    "PipelineContext",
    "PipelineStage",
    "ResultAggregator",
    "AggregatedResult",
    "PipelineConfidenceScorer",
    "ConfidenceProfile",
]
