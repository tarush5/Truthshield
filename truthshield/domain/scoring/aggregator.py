"""
Trust scoring.

Rewritten rather than ported, because the previous aggregator's failures were
structural and the new `DetectorStatus` model makes the correct version much
smaller. The rules it now obeys, each of which was violated before:

1. **A detector that did not run contributes nothing.** Detectors failed open,
   returning 0.0 ("no manipulation") when their model would not load, and that
   fed the score as a positive signal.

2. **Manipulation evidence is not evidence of truth.** The old code promoted
   the ML manipulation score into `support_score`, which the verdict function
   read as "sources support this claim". A clean-looking image with no
   readable text was therefore VERIFIED at 85% trust. "This photo isn't
   doctored" says nothing about whether the caption is true.

3. **Nothing checked means no verdict.** With no claim verdicts, or with every
   claim unresolved, the result is INSUFFICIENT EVIDENCE — not a number
   assembled out of component defaults and labelled PARTIALLY TRUE.

4. **Confidence is reported, not buried.** The band reflects how much actually
   ran, and the caller sees which checks were skipped.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Sequence

from truthshield.domain.types import (
    ClaimVerdict, ConfidenceBand, ContentPacket, DetectorResult,
    Stance, TrustBreakdown, Verdict,
)

logger = logging.getLogger(__name__)

# Weights for the four reported components. They sum to 1.0.
W_FACT_MATCH = 0.40
W_EVIDENCE_STRENGTH = 0.25
W_SOURCE_CREDIBILITY = 0.20
W_MANIPULATION = 0.15

# Verdict bands, in trust points. Shared with the frontend dial so the number
# and the label can never tell the reader two different stories.
BANDS = {
    Verdict.VERIFIED: (85, 100),
    Verdict.LIKELY_TRUE: (65, 84),
    Verdict.PARTIALLY_TRUE: (45, 64),
    Verdict.MIXED_EVIDENCE: (45, 64),
    Verdict.INSUFFICIENT_EVIDENCE: (40, 60),
    Verdict.MISLEADING: (25, 44),
    Verdict.LIKELY_FALSE: (15, 44),
    Verdict.FALSE: (0, 25),
}


@dataclass
class ScoringResult:
    verdict: Verdict
    trust_score: int
    confidence_band: ConfidenceBand
    breakdown: TrustBreakdown
    reasons: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)


class TrustScorer:
    def score(
        self,
        packet: ContentPacket,
        claim_verdicts: Sequence[ClaimVerdict],
        detectors: Sequence[DetectorResult],
    ) -> ScoringResult:
        reasons: List[str] = []
        limitations = self._limitations(packet, claim_verdicts, detectors)

        manipulation = self._manipulation_risk(detectors, reasons)

        # ── Gate: was anything actually fact-checked? ────────────
        decided = [cv for cv in claim_verdicts if cv.verdict.is_decided]
        if not claim_verdicts or not decided:
            return self._undecided(packet, claim_verdicts, manipulation, reasons, limitations)

        fact_match = self._fact_match(decided)
        evidence_strength = self._evidence_strength(decided)
        source_credibility = self._source_credibility(decided, reasons)

        weighted = (
            W_FACT_MATCH * fact_match
            + W_EVIDENCE_STRENGTH * evidence_strength
            + W_SOURCE_CREDIBILITY * source_credibility
            + W_MANIPULATION * (1.0 - manipulation)
        )

        verdict = self._verdict_from_claims(decided)
        trust = self._clamp_to_band(round(weighted * 100), verdict)
        band = self._confidence(decided, detectors)

        self._explain(decided, reasons)

        return ScoringResult(
            verdict=verdict,
            trust_score=trust,
            confidence_band=band,
            breakdown=TrustBreakdown(
                fact_match=round(fact_match * 100, 1),
                evidence_strength=round(evidence_strength * 100, 1),
                source_credibility=round(source_credibility * 100, 1),
                manipulation_risk=round(manipulation * 100, 1),
            ),
            reasons=reasons,
            limitations=limitations,
        )

    # ──────────────────────────────────────────────────────────

    def _undecided(self, packet, claim_verdicts, manipulation, reasons, limitations) -> ScoringResult:
        """
        Nothing was settled. Say so.

        The one thing still worth asserting is positively detected
        manipulation: if a detector that genuinely ran found strong evidence of
        tampering, that stands on its own even with no claim checked.
        """
        verdict = Verdict.INSUFFICIENT_EVIDENCE
        trust = 50

        if manipulation >= 0.60:
            verdict = Verdict.LIKELY_FALSE
            trust = self._clamp_to_band(round((1.0 - manipulation) * 100), verdict)
            reasons.append("Signs of manipulation were detected in the media itself")

        if not claim_verdicts:
            if not packet.has_text:
                limitations.insert(0, "No readable text could be extracted, so no claim was fact-checked")
            else:
                limitations.insert(0, "No verifiable claim was found in this content")
        else:
            limitations.insert(0, "Claims were checked but no source settled them either way")

        return ScoringResult(
            verdict=verdict,
            trust_score=trust,
            # Never HIGH: by definition little was established.
            confidence_band=ConfidenceBand.LOW,
            breakdown=TrustBreakdown(
                fact_match=50.0,
                evidence_strength=0.0,
                source_credibility=0.0,
                manipulation_risk=round(manipulation * 100, 1),
            ),
            reasons=reasons,
            limitations=limitations,
        )

    def _manipulation_risk(self, detectors: Sequence[DetectorResult], reasons: List[str]) -> float:
        """
        Mean score across detectors that actually ran.

        Returns a neutral 0.5 when none ran — not 0.0. Zero would read as
        "verified clean" and is exactly how a missing torch install used to
        become a positive trust signal.
        """
        usable = [d for d in detectors if d.counts_toward_scoring]
        if not usable:
            return 0.5

        for d in usable:
            if d.score >= 0.60:
                reasons.append(f"{d.name.replace('_', ' ').title()}: signs of manipulation ({d.score:.0%})")
        return sum(d.score for d in usable) / len(usable)

    def _fact_match(self, decided: Sequence[ClaimVerdict]) -> float:
        value = {
            Verdict.VERIFIED: 1.0,
            Verdict.LIKELY_TRUE: 0.85,
            Verdict.PARTIALLY_TRUE: 0.55,
            Verdict.MISLEADING: 0.30,
            Verdict.LIKELY_FALSE: 0.15,
            Verdict.FALSE: 0.0,
        }
        # Weighted by each claim's own confidence, pulled toward neutral when
        # that confidence is low.
        total = 0.0
        for cv in decided:
            base = value.get(cv.verdict, 0.5)
            total += base * cv.confidence + 0.5 * (1 - cv.confidence)
        return total / len(decided)

    def _evidence_strength(self, decided: Sequence[ClaimVerdict]) -> float:
        """How much evidence took a position, and how much of it there was."""
        all_items = [e for cv in decided for e in cv.evidence]
        if not all_items:
            return 0.0
        sided = [e for e in all_items if e.stance in (Stance.SUPPORTS, Stance.REFUTES)]
        stance_ratio = len(sided) / len(all_items)
        volume = min(1.0, len(sided) / 4.0)
        return round(0.6 * stance_ratio + 0.4 * volume, 4)

    def _source_credibility(self, decided: Sequence[ClaimVerdict], reasons: List[str]) -> float:
        """Credibility of the sources that actually took a position."""
        sided = [
            e for cv in decided for e in cv.evidence
            if e.stance in (Stance.SUPPORTS, Stance.REFUTES)
        ]
        if not sided:
            return 0.0
        top = sorted(sided, key=lambda e: e.source_score, reverse=True)[:5]
        authoritative = [e for e in top if e.source_score >= 0.90]
        if authoritative:
            names = ", ".join(sorted({e.source_domain or e.url.split("/")[2] for e in authoritative})[:2])
            reasons.append(f"Authoritative source(s) addressed this claim ({names})")
        return sum(e.source_score for e in top) / len(top)

    def _verdict_from_claims(self, decided: Sequence[ClaimVerdict]) -> Verdict:
        """
        The overall verdict is driven by the claims, never by detector output.

        A single clearly-false claim outweighs several true ones: content that
        contains a falsehood is not "mostly true".
        """
        if any(cv.verdict is Verdict.FALSE for cv in decided):
            return Verdict.FALSE
        if any(cv.verdict is Verdict.LIKELY_FALSE for cv in decided):
            return Verdict.LIKELY_FALSE
        if any(cv.verdict is Verdict.MISLEADING for cv in decided):
            return Verdict.MISLEADING

        leaning_true = [cv for cv in decided if cv.verdict.leans_true]
        if len(leaning_true) != len(decided):
            return Verdict.PARTIALLY_TRUE

        mean_conf = sum(cv.confidence for cv in decided) / len(decided)
        if all(cv.verdict is Verdict.VERIFIED for cv in decided) and mean_conf >= 0.80:
            return Verdict.VERIFIED
        if mean_conf >= 0.45:
            return Verdict.LIKELY_TRUE
        return Verdict.PARTIALLY_TRUE

    def _clamp_to_band(self, score: int, verdict: Verdict) -> int:
        low, high = BANDS[verdict]
        return max(low, min(high, score))

    def _confidence(self, decided, detectors) -> ConfidenceBand:
        """
        How much of the system actually contributed.

        Driven by the volume of sided evidence and by how many detectors ran,
        so a result assembled from very little cannot be presented as certain.
        """
        sided = sum(
            1 for cv in decided for e in cv.evidence
            if e.stance in (Stance.SUPPORTS, Stance.REFUTES)
        )
        mean_conf = sum(cv.confidence for cv in decided) / max(len(decided), 1)
        ran = sum(1 for d in detectors if d.counts_toward_scoring)
        applicable = sum(1 for d in detectors if d.status.value != "not_applicable")
        coverage = ran / applicable if applicable else 1.0

        if sided >= 4 and mean_conf >= 0.60 and coverage >= 0.5:
            return ConfidenceBand.HIGH
        if sided >= 2 and mean_conf >= 0.40:
            return ConfidenceBand.MODERATE
        if sided >= 1:
            return ConfidenceBand.LOW
        return ConfidenceBand.VERY_LOW

    def _explain(self, decided: Sequence[ClaimVerdict], reasons: List[str]) -> None:
        supports = sum(len(cv.supporting) for cv in decided)
        refutes = sum(len(cv.refuting) for cv in decided)
        if supports:
            reasons.append(f"Supported by {supports} source{'s' if supports != 1 else ''}")
        if refutes:
            reasons.append(f"Contradicted by {refutes} source{'s' if refutes != 1 else ''}")

    def _limitations(self, packet, claim_verdicts, detectors) -> List[str]:
        """
        What this analysis could not do.

        Shown to the reader. The previous report asserted the opposite —
        "No contradicting visual deepfake or anomalies detected" and "Voice
        authenticity verified" appeared on text-only submissions that had no
        video or audio to clear.
        """
        out: List[str] = []
        for d in detectors:
            if d.status.value == "unavailable":
                out.append(f"{d.name.replace('_', ' ').title()} check could not run: {d.detail}")
            elif d.status.value == "error":
                out.append(f"{d.name.replace('_', ' ').title()} check failed: {d.detail}")
        if claim_verdicts and not any(cv.evidence for cv in claim_verdicts):
            out.append("No evidence was retrieved for the extracted claims")
        return out
