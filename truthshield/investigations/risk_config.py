"""
Risk engine configuration.

Weights are configuration, not code. The defaults are the spec's starting
point; a deployment overrides any subset with `RISK_WEIGHTS_JSON`, e.g.

    RISK_WEIGHTS_JSON='{"weights": {"url": 25, "nlp": 15}, "thresholds": {"critical": 90}}'

Every assessment records the configuration it was computed with
(`version` plus the resolved values), so a score can always be explained
against the weights that actually produced it -- including after they change.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Dict

from truthshield.investigations.types import Family

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS: Dict[str, float] = {
    Family.NLP.value: 20,
    Family.URL.value: 20,
    Family.REPUTATION.value: 15,
    Family.BEHAVIORAL.value: 15,
    Family.DOCUMENT_MEDIA.value: 15,
    Family.EVIDENCE.value: 15,
}

# Lower bounds of each level. LOW is everything below MEDIUM.
DEFAULT_THRESHOLDS: Dict[str, float] = {"medium": 40, "high": 65, "critical": 85}

# Confidence ceilings (see risk.py for why each exists).
HEURISTIC_ONLY_CONFIDENCE_CAP = 0.85
NO_SIGNAL_CONFIDENCE_CAP = 0.35


@dataclass(frozen=True)
class RiskConfig:
    weights: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    thresholds: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_THRESHOLDS))
    source: str = "default"

    @property
    def version(self) -> str:
        """Stable fingerprint of the resolved values."""
        blob = json.dumps({"w": self.weights, "t": self.thresholds}, sort_keys=True)
        return f"{self.source}-{hashlib.sha256(blob.encode()).hexdigest()[:8]}"

    def reliability(self, family: str) -> float:
        top = max(self.weights.values()) or 1.0
        return max(0.0, min(1.0, self.weights.get(family, 0.0) / top))

    def as_dict(self) -> dict:
        return {"version": self.version, "weights": self.weights, "thresholds": self.thresholds}


def load_risk_config() -> RiskConfig:
    from truthshield.settings import get_settings

    raw = get_settings().RISK_WEIGHTS_JSON.strip()
    if not raw:
        return RiskConfig()

    try:
        data = json.loads(raw)
        weights = dict(DEFAULT_WEIGHTS)
        for key, value in (data.get("weights") or {}).items():
            if key not in weights:
                raise ValueError(f"unknown family '{key}'")
            if float(value) < 0:
                raise ValueError(f"weight for '{key}' is negative")
            weights[key] = float(value)
        thresholds = dict(DEFAULT_THRESHOLDS)
        for key, value in (data.get("thresholds") or {}).items():
            if key not in thresholds:
                raise ValueError(f"unknown threshold '{key}'")
            thresholds[key] = float(value)
        if not thresholds["medium"] < thresholds["high"] < thresholds["critical"]:
            raise ValueError("thresholds must satisfy medium < high < critical")
        if max(weights.values()) <= 0:
            raise ValueError("at least one weight must be positive")
        return RiskConfig(weights=weights, thresholds=thresholds, source="custom")
    except (ValueError, TypeError, AttributeError) as exc:
        # Loud, and fail back to defaults rather than scoring with half a config.
        logger.error("RISK_WEIGHTS_JSON is invalid (%s); using default weights.", exc)
        return RiskConfig()
