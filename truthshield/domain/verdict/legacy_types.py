"""
Types the ported engines were written against.

The engines in this package came over from the previous implementation whole,
to avoid reintroducing the accuracy bugs they encode fixes for. They were
written against a slightly different set of models than
`truthshield.domain.types`, so rather than editing a thousand lines of tuned
logic, the shapes they expect live here and `adapters.py` converts at the
boundary.

`Evidence.stance` is a plain string and `Verdict` a small enum on purpose:
that is what the ported code assigns and compares against.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Verdict(str, Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    MISLEADING = "MISLEADING"
    UNVERIFIED = "UNVERIFIED"


class Claim(BaseModel):
    text: str
    entity: Optional[str] = None
    date: Optional[str] = None
    location: Optional[str] = None


class Evidence(BaseModel):
    title: str
    url: str
    snippet: str = ""
    source_score: float = 0.5
    stance: str = "NEUTRAL"

    # Set when `url` is an aggregator interstitial that does not name the
    # publisher; the ranker scores this in preference to the URL.
    source_domain: Optional[str] = None


class ClaimVerdict(BaseModel):
    claim: Claim
    verdict: Verdict = Verdict.UNVERIFIED
    reasoning: str = ""
    confidence: float = 0.0
    evidence: List[Evidence] = Field(default_factory=list)
