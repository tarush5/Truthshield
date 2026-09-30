"""
Central risk engine.

One place turns every engine's signals into a 0-100 risk score, a level, a
separate confidence, and a per-signal breakdown whose points sum to the
score. The method, and why each step is shaped the way it is:

1. **Family score.** A family's signals combine through 1.x's
   `score_from_indicators`: contributions decay by rank (1, 0.72, 0.52 ...)
   and a lone signal is capped at 45. One keyword cannot reach CRITICAL.

2. **Noisy-OR across families.** With reliability r_f = w_f / max(w):

       risk = 100 * (1 - prod_f (1 - r_f * s_f / 100))

   A family that found nothing contributes a factor of 1. So, unlike a
   weighted average, three clean checks cannot dilute one confident phishing
   finding, while independent families that agree compound.

   The result is capped at 99: the scale stays open at the top because no
   combination of signals amounts to proof.

3. **Exact attribution.** Family f receives risk * a_f / sum(a), with
   a_f = -ln(1 - r_f * s_f / 100) -- its exact share of the log-product --
   then splits it across its signals by decayed contribution. Points are
   rounded by largest remainder, so the displayed breakdown sums to the
   displayed score.

4. **Confidence is a second axis.** Risk says how bad it looks; confidence
   says how much of the system looked and how sure the leading signals are.
   High risk at low confidence ("looks bad, not sure") is a real state that a
   single number cannot express.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Sequence, Set

from pydantic import BaseModel, Field

from truthshield.fraud.contract import score_from_indicators
from truthshield.investigations.risk_config import (
    HEURISTIC_ONLY_CONFIDENCE_CAP, NO_SIGNAL_CONFIDENCE_CAP, RiskConfig, load_risk_config,
)
from truthshield.investigations.types import EngineResult, EngineStatus, Provenance, Signal

REPRESENTS = (
    "Estimated risk that this content is part of a fraud, phishing or manipulation "
    "attempt, computed only from the signals listed. It is not proof, and a low score "
    "is not a guarantee of safety."
)

DECAY = 0.72
MAX_SCORE = 99.0


class Contribution(BaseModel):
    code: str
    title: str
    family: str
    severity: str
    provenance: str
    engine: str
    engine_version: str
    points: int
    confidence: float
    evidence: str | None = None
    explanation: str = ""


class FamilyScore(BaseModel):
    score: float
    weight: float
    reliability: float
    assessed: bool
    signals: int
    points: int


class RiskAssessment(BaseModel):
    score: int
    level: str
    confidence: float
    confidence_band: str
    represents: str = REPRESENTS
    contributions: List[Contribution] = Field(default_factory=list)
    families: Dict[str, FamilyScore] = Field(default_factory=dict)
    config: dict = Field(default_factory=dict)
    notes: List[str] = Field(default_factory=list)


def level_for(score: float, config: RiskConfig) -> str:
    t = config.thresholds
    if score >= t["critical"]:
        return "CRITICAL"
    if score >= t["high"]:
        return "HIGH"
    if score >= t["medium"]:
        return "MEDIUM"
    return "LOW"


def band_for(confidence: float) -> str:
    if confidence >= 0.75:
        return "HIGH"
    if confidence >= 0.5:
        return "MODERATE"
    if confidence >= 0.3:
        return "LOW"
    return "VERY_LOW"


def _largest_remainder(values: Sequence[float], total: int) -> List[int]:
    floors = [math.floor(v) for v in values]
    shortfall = total - sum(floors)
    order = sorted(range(len(values)), key=lambda i: -(values[i] - floors[i]))
    for i in order[: max(0, shortfall)]:
        floors[i] += 1
    return floors


class RiskEngine:
    def __init__(self, config: RiskConfig | None = None):
        self.config = config or load_risk_config()

    def assess(
        self,
        signals: Iterable[Signal],
        engines: Sequence[EngineResult],
        assessed_families: Set[str],
    ) -> RiskAssessment:
        scoring = [s for s in signals if s.contribution > 0]
        by_family: Dict[str, List[Signal]] = {f: [] for f in self.config.weights}
        for signal in scoring:
            by_family.setdefault(signal.family.value, []).append(signal)

        # ── 1-2. Family scores and noisy-OR ──────────────────
        family_raw: Dict[str, float] = {}
        product = 1.0
        log_shares: Dict[str, float] = {}
        for family, members in by_family.items():
            s_f = score_from_indicators(members) if members else 0.0
            family_raw[family] = s_f
            x = min(0.999, self.config.reliability(family) * s_f / 100.0)
            product *= 1.0 - x
            log_shares[family] = -math.log(1.0 - x) if x > 0 else 0.0

        # Open at the top: no combination of signals is proof, so the scale
        # never displays 100. A heuristic "100/100" reads as certainty.
        risk = min(MAX_SCORE, 100.0 * (1.0 - product))
        score = int(round(risk))

        # ── 3. Attribution ───────────────────────────────────
        total_log = sum(log_shares.values())
        raw_points: List[float] = []
        ordered: List[Signal] = []
        family_points: Dict[str, float] = {}
        for family, members in by_family.items():
            share = risk * log_shares[family] / total_log if total_log > 0 else 0.0
            family_points[family] = share
            ranked = sorted(members, key=lambda s: -s.contribution)
            decayed = [s.contribution * DECAY ** i for i, s in enumerate(ranked)]
            weight_sum = sum(decayed) or 1.0
            for signal, d in zip(ranked, decayed):
                ordered.append(signal)
                raw_points.append(share * d / weight_sum)

        points = _largest_remainder(raw_points, score) if ordered else []
        contributions = [
            Contribution(
                code=s.code, title=s.title, family=s.family.value, severity=s.severity.value,
                provenance=s.provenance.value, engine=s.engine, engine_version=s.engine_version,
                points=p, confidence=round(s.confidence, 2), evidence=s.evidence,
                explanation=s.explanation,
            )
            for s, p in zip(ordered, points)
        ]
        contributions.sort(key=lambda c: -c.points)

        families = {}
        for family, members in by_family.items():
            family_int = sum(c.points for c in contributions if c.family == family)
            families[family] = FamilyScore(
                score=round(family_raw[family], 1),
                weight=self.config.weights.get(family, 0.0),
                reliability=round(self.config.reliability(family), 3),
                assessed=family in assessed_families,
                signals=len(members),
                points=family_int,
            )

        # ── 4. Confidence ────────────────────────────────────
        confidence, notes = self._confidence(scoring, contributions, engines, family_raw)

        return RiskAssessment(
            score=score,
            level=level_for(score, self.config),
            confidence=round(confidence, 2),
            confidence_band=band_for(confidence),
            contributions=contributions,
            families=families,
            config=self.config.as_dict(),
            notes=notes,
        )

    def _confidence(self, scoring, contributions, engines, family_raw):
        notes: List[str] = []
        applicable = [e for e in engines if e.status is not EngineStatus.NOT_APPLICABLE]
        ran = [e for e in applicable if e.status is EngineStatus.OK]
        coverage = len(ran) / len(applicable) if applicable else 0.0
        if len(ran) < len(applicable):
            skipped = ", ".join(e.engine for e in applicable if e.status is not EngineStatus.OK)
            notes.append(f"Not every applicable engine ran ({skipped}); confidence is reduced accordingly.")

        if not scoring:
            confidence = min(NO_SIGNAL_CONFIDENCE_CAP, 0.15 + 0.2 * coverage)
            notes.append(
                "No risk signal fired. Absence of detected signals is weak evidence of safety, "
                "so confidence is capped."
            )
            return confidence, notes

        lead = [c for c in contributions if c.points > 0][:3] or contributions[:3]
        total = sum(c.points for c in lead) or 1
        lead_conf = sum(c.confidence * (c.points or 1) for c in lead) / max(total, len(lead))
        confidence = coverage * (0.45 + 0.5 * lead_conf)

        agreeing = sum(1 for v in family_raw.values() if v >= 40)
        if agreeing >= 2:
            confidence += 0.08
            notes.append(f"{agreeing} independent signal families agree, which raises confidence.")

        corroborated = any(
            s.provenance in (Provenance.RETRIEVED, Provenance.ML_PREDICTION) for s in scoring
        )
        if not corroborated and confidence > HEURISTIC_ONLY_CONFIDENCE_CAP:
            confidence = HEURISTIC_ONLY_CONFIDENCE_CAP
            notes.append(
                "All signals are rule-based heuristics with no retrieved or model-based "
                "corroboration, so confidence is capped."
            )
        return max(0.0, min(1.0, confidence)), notes
