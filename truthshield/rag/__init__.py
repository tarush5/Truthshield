"""
Evidence store and retrieval-augmented evidence gathering (2.0 Phase 2).

Distinct from `truthshield.domain.rag`, the 1.x prior-claim memory and
grounded explanation, which the fact-check endpoints still use.
"""

from truthshield.rag.engine import RAGEngine, Retrieval
from truthshield.rag.store import Candidate, EvidenceStore, Filters

__all__ = ["Candidate", "EvidenceStore", "Filters", "RAGEngine", "Retrieval"]
