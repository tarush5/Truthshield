"""
Detector evaluation on a labelled set.

    python -m truthshield.investigations.evaluation [path.jsonl]

Runs each item through the same text and URL engines and risk engine the
pipeline uses (offline: no page fetch, no evidence retrieval) and reports
how often the result agrees with the label.

The default set, `tests/eval/fraud_eval.jsonl`, is small and was written for
this project: invented scam and benign messages, emails and URLs. Numbers
from it measure *regressions in the rules*, not real-world accuracy, and
must never be presented as the latter.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

DEFAULT_SET = Path(__file__).resolve().parents[2] / "tests" / "eval" / "fraud_eval.jsonl"

# A result at or above MEDIUM is a "flag": the UI tells the user to be careful.
FLAG_LEVELS = {"MEDIUM", "HIGH", "CRITICAL"}


@dataclass
class Outcome:
    id: str
    label: str
    kind: str
    score: int
    level: str
    classification: str
    top_signals: List[str]
    type: str = ""
    language: str = ""
    length: str = ""
    confidence: float = 0.0

    @property
    def flagged(self) -> bool:
        return self.level in FLAG_LEVELS

    @property
    def correct(self) -> bool:
        return self.flagged == (self.label == "fraud")


def load(path: Optional[Path] = None) -> List[dict]:
    with open(path or DEFAULT_SET, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def assess(item: dict) -> Outcome:
    from truthshield.investigations import explain
    from truthshield.investigations.engines import analysis_engines
    from truthshield.investigations.risk import RiskEngine
    from truthshield.investigations.types import EngineStatus, InvestigationContext, InvestigationType

    content = item["content"]
    kind = InvestigationType(item["type"])
    ctx = InvestigationContext(
        investigation_id=f"eval-{item['id']}", type=kind, content=content, text=content,
        input_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(), allow_page_fetch=False,
    )
    text_engine, url_engine = analysis_engines()
    text = text_engine.run(ctx)
    ctx.artifacts.update(text.artifacts)
    if text.status is EngineStatus.NOT_APPLICABLE and kind is InvestigationType.URL:
        ctx.urls = [content.strip()]
    url = url_engine.run(ctx)

    engines = [text, url]
    families = {"text": {"nlp"}, "url": {"url"}}
    assessed = set()
    for engine in engines:
        if engine.status is EngineStatus.OK:
            assessed |= families.get(engine.engine, set())
    assessment = RiskEngine().assess([s for e in engines for s in e.signals], engines, assessed)
    classification, _ = explain.classify(assessment, engines)
    chars = len(content)
    return Outcome(
        id=item["id"], label=item["label"], kind=item.get("kind", ""),
        score=assessment.score, level=assessment.level, classification=classification,
        top_signals=[c.code for c in assessment.contributions if c.points > 0][:4],
        type=item["type"],
        # Detected, not labelled: the breakdown shows how the engine saw it.
        language=item.get("lang") or (text.artifacts.get("language", {}).get("detected") or "-"),
        length="short (<80)" if chars < 80 else "medium (80-199)" if chars < 200 else "long (200+)",
        confidence=assessment.confidence,
    )


def wilson(k: int, n: int, z: float = 1.96) -> Optional[List[float]]:
    """95% Wilson score interval for k successes in n trials; None when n is 0."""
    if not n:
        return None
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
    return [round(max(0.0, centre - half), 3), round(min(1.0, centre + half), 3)]


def _scores(outcomes: List[Outcome]) -> dict:
    tp = sum(1 for o in outcomes if o.label == "fraud" and o.flagged)
    fn = sum(1 for o in outcomes if o.label == "fraud" and not o.flagged)
    fp = sum(1 for o in outcomes if o.label == "benign" and o.flagged)
    tn = sum(1 for o in outcomes if o.label == "benign" and not o.flagged)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "items": len(outcomes),
        "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(2 * precision * recall / (precision + recall), 3) if precision + recall else 0.0,
        "false_positive_rate": round(fp / (fp + tn), 3) if fp + tn else 0.0,
        "false_negative_rate": round(fn / (fn + tp), 3) if fn + tp else 0.0,
        # Small sets give wide intervals; read every rate with its interval.
        "ci95": {
            "precision": wilson(tp, tp + fp),
            "recall": wilson(tp, tp + fn),
            "false_positive_rate": wilson(fp, fp + tn),
        },
    }


def calibration(outcomes: List[Outcome]) -> dict:
    """
    Reliability by confidence band: how often the verdict (flagged or not)
    was right, next to the confidence the system stated.

    Confidence here is "how sure the system is of its assessment", so a
    well-calibrated band has accuracy close to its mean confidence. The gap
    is the item-weighted mean of |accuracy - mean confidence| over bands.
    Measured, never fitted: nothing here adjusts the confidence formula.
    """
    from truthshield.investigations.risk import band_for

    bands: dict = {}
    for o in outcomes:
        bands.setdefault(band_for(o.confidence), []).append(o)
    table = {}
    gap = 0.0
    # Brier score of confidence read as P(verdict correct). Lower is better;
    # it is only meaningful because the verdict is checked against a label.
    brier = (sum((o.confidence - (1.0 if o.correct else 0.0)) ** 2 for o in outcomes) / len(outcomes)
             if outcomes else None)
    for band in ("VERY_LOW", "LOW", "MODERATE", "HIGH"):
        members = bands.get(band, [])
        if not members:
            continue
        accuracy = sum(o.correct for o in members) / len(members)
        mean_conf = sum(o.confidence for o in members) / len(members)
        gap += len(members) * abs(accuracy - mean_conf)
        table[band] = {"items": len(members), "accuracy": round(accuracy, 3),
                       "mean_confidence": round(mean_conf, 3),
                       "flagged": sum(o.flagged for o in members)}
    return {"bands": table, "weighted_gap": round(gap / len(outcomes), 3) if outcomes else None,
            "brier": round(brier, 3) if brier is not None else None}


def evaluate(items: Iterable[dict]) -> dict:
    outcomes = [assess(item) for item in items]
    groups = {
        dim: sorted({getattr(o, dim) for o in outcomes})
        for dim in ("type", "language", "length")
    }
    return {
        **_scores(outcomes),
        # Per slice: where the rules are strong or weak. Slices are small;
        # read them as pointers to look at, not as rates.
        "by": {
            dim: {value: _scores([o for o in outcomes if getattr(o, dim) == value]) for value in values}
            for dim, values in groups.items()
        },
        "recall_by_kind": {
            kind: _scores([o for o in outcomes if o.kind == kind])["recall"]
            for kind in sorted({o.kind for o in outcomes if o.label == "fraud"})
        },
        "fpr_by_kind": {
            kind: _scores([o for o in outcomes if o.kind == kind])["false_positive_rate"]
            for kind in sorted({o.kind for o in outcomes if o.label == "benign"})
        },
        "calibration": calibration(outcomes),
        "errors": [o for o in outcomes if not o.correct],
        "outcomes": outcomes,
    }


def main(argv: List[str]) -> int:
    paths = [a for a in argv[1:] if not a.startswith("--")]
    report = evaluate(load(Path(paths[0]) if paths else None))
    print(f"{report['items']} items  precision {report['precision']:.3f}  recall {report['recall']:.3f}  "
          f"F1 {report['f1']:.3f}  FPR {report['false_positive_rate']:.3f}  FNR {report['false_negative_rate']:.3f}")
    ci = report["ci95"]
    fmt = lambda v: f"[{v[0]:.2f}, {v[1]:.2f}]" if v else "n/a"  # noqa: E731
    print(f"  95% CI  precision {fmt(ci['precision'])}  recall {fmt(ci['recall'])}  "
          f"FPR {fmt(ci['false_positive_rate'])}")
    print(f"  confusion matrix (rows = label):  fraud -> flagged {report['tp']:>3}  not flagged {report['fn']:>3}")
    print(f"                                    benign -> flagged {report['fp']:>3}  not flagged {report['tn']:>3}")
    if "--by" in argv:
        for dim, slices in report["by"].items():
            for value, m in slices.items():
                print(f"  {dim:<9} {value:<16} n={m['items']:>3}  P {m['precision']:.2f}  R {m['recall']:.2f}  "
                      f"FPR {m['false_positive_rate']:.2f}")
    if "--calibration" in argv:
        for band, b in report["calibration"]["bands"].items():
            print(f"  confidence {band:<9} n={b['items']:>3}  accuracy {b['accuracy']:.2f}  "
                  f"mean confidence {b['mean_confidence']:.2f}  flagged {b['flagged']}")
        print(f"  weighted |accuracy - confidence| gap: {report['calibration']['weighted_gap']}  "
              f"Brier: {report['calibration']['brier']}")
    for o in report["errors"]:
        miss = "MISSED" if o.label == "fraud" else "FALSE ALARM"
        print(f"  {miss:<11} {o.id:<14} {o.score:>3} {o.level:<8} {o.classification:<26} {', '.join(o.top_signals)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
