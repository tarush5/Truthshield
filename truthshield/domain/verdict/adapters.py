"""
Boundary between the ported engines and the domain model.

The engines in this package were brought over whole (see the note at the top
of `engine.py`) and speak `legacy_types`. Everything outside speaks
`truthshield.domain.types`. Converting in one place keeps that seam explicit
and stops the older vocabulary leaking into the API.
"""

from __future__ import annotations

from typing import List

from truthshield.domain import types as domain
from truthshield.domain.verdict import legacy_types as legacy

# The engines emit four verdicts; the product reports eight. Confidence
# decides how firmly a TRUE/FALSE is stated, so a weakly-supported result is
# not presented with the same force as a well-evidenced one.
_CONFIDENT = 0.70


def to_legacy_claim(claim: domain.Claim) -> legacy.Claim:
    return legacy.Claim(
        text=claim.text, entity=claim.entity, date=claim.date, location=claim.location
    )


def to_legacy_evidence(item: domain.EvidenceItem) -> legacy.Evidence:
    return legacy.Evidence(
        title=item.title,
        url=item.url,
        snippet=item.snippet,
        source_score=item.source_score,
        stance=item.stance.value,
        source_domain=item.source_domain,
    )


def from_legacy_evidence(item: legacy.Evidence) -> domain.EvidenceItem:
    return domain.EvidenceItem(
        title=item.title,
        url=item.url,
        snippet=item.snippet,
        source_score=item.source_score,
        stance=_stance(item.stance),
        source_domain=getattr(item, "source_domain", None),
    )


def _stance(raw: str) -> domain.Stance:
    value = (raw or "NEUTRAL").upper()
    if value == "SUPPORTS":
        return domain.Stance.SUPPORTS
    if value == "REFUTES":
        return domain.Stance.REFUTES
    # The engines use INSUFFICIENT for "does not address this claim".
    if value == "INSUFFICIENT":
        return domain.Stance.OFF_TOPIC
    return domain.Stance.NEUTRAL


def _verdict(raw: legacy.Verdict, confidence: float) -> domain.Verdict:
    if raw is legacy.Verdict.TRUE:
        return domain.Verdict.VERIFIED if confidence >= _CONFIDENT else domain.Verdict.LIKELY_TRUE
    if raw is legacy.Verdict.FALSE:
        return domain.Verdict.FALSE if confidence >= _CONFIDENT else domain.Verdict.LIKELY_FALSE
    if raw is legacy.Verdict.MISLEADING:
        return domain.Verdict.MISLEADING
    return domain.Verdict.INSUFFICIENT_EVIDENCE


def from_legacy_claim_verdict(cv: legacy.ClaimVerdict) -> domain.ClaimVerdict:
    return domain.ClaimVerdict(
        claim=domain.Claim(
            text=cv.claim.text,
            entity=cv.claim.entity,
            date=cv.claim.date,
            location=cv.claim.location,
        ),
        verdict=_verdict(cv.verdict, cv.confidence),
        confidence=cv.confidence,
        reasoning=cv.reasoning,
        evidence=[from_legacy_evidence(e) for e in cv.evidence],
    )


def from_legacy_claim_verdicts(items: List[legacy.ClaimVerdict]) -> List[domain.ClaimVerdict]:
    return [from_legacy_claim_verdict(cv) for cv in items]
