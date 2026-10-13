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
    return Outcome(
        id=item["id"], label=item["label"], kind=item.get("kind", ""),
        score=assessment.score, level=assessment.level, classification=classification,
        top_signals=[c.code for c in assessment.contributions if c.points > 0][:4],
    )


def evaluate(items: Iterable[dict]) -> dict:
    outcomes = [assess(item) for item in items]
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
        "errors": [o for o in outcomes if not o.correct],
        "outcomes": outcomes,
    }


def main(argv: List[str]) -> int:
    report = evaluate(load(Path(argv[1]) if len(argv) > 1 else None))
    print(f"{report['items']} items  precision {report['precision']:.3f}  recall {report['recall']:.3f}  "
          f"F1 {report['f1']:.3f}  FPR {report['false_positive_rate']:.3f}  "
          f"(tp {report['tp']} fn {report['fn']} fp {report['fp']} tn {report['tn']})")
    for o in report["errors"]:
        miss = "MISSED" if o.label == "fraud" else "FALSE ALARM"
        print(f"  {miss:<11} {o.id:<14} {o.score:>3} {o.level:<8} {o.classification:<26} {', '.join(o.top_signals)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
