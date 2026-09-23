"""
Retrieval-augmented generation, in the two places it earns its keep.

`store`      A semantic memory of claims already adjudicated. Misinformation
             repeats, so the second arrival of a claim should be cheap and
             should tell the reader we have seen it before.

`grounding`  A short explanation written *from* the retrieved sources, with
             every citation verified against the real source list before a
             reader sees it. The verdict is never taken from the model.

Both degrade to nothing in particular: no embeddings means the memory falls
back to token overlap, and no API key means there is no generated
explanation and the engine's own reasoning is shown instead. Neither is an
error path, and both are the default configuration.
"""

from truthshield.domain.rag.grounding import (
    GroundedExplanation,
    build_context,
    explain,
)
from truthshield.domain.rag.store import (
    NEAR_DUPLICATE,
    RELATED,
    ClaimMemory,
    PriorClaim,
    get_claim_memory,
)

__all__ = [
    "ClaimMemory",
    "GroundedExplanation",
    "NEAR_DUPLICATE",
    "PriorClaim",
    "RELATED",
    "build_context",
    "explain",
    "get_claim_memory",
]
