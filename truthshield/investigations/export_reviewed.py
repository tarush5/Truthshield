"""
Export reviewer-labelled investigations as an evaluation set.

    python -m truthshield.investigations.export_reviewed --out reviewed.jsonl --confirm-consent

Real, independently labelled messages are the only route to an honest
real-world accuracy figure; the author-written sets in tests/eval cannot
provide one. This turns resolved appeals into labelled items:

* only **appeals** (the submitter asked for a human to look) whose latest
  reviewer decision is `fraud` or `legitimate`; `inconclusive` is skipped;
* only text inputs, and only their **redacted** copy -- the original is
  never exported. Redaction masks cards, codes, phone numbers and similar,
  which a reader of the results should remember;
* one item per template: near-identical submissions keep the first;
* each item carries a stable `split` from `dataset.assign_split`, so it
  stays in the same split as the set grows and campaign variants land
  together. Measure on `test`, never tune on it.

Whether users' submissions may be used this way is a policy and consent
decision for the operator. The flag `--confirm-consent` records that it was
made; the export refuses to run without it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List


def collect(session) -> List[dict]:
    from truthshield.infra.models import InvestigationReview
    from truthshield.investigations.dataset import assign_split, template

    rows = (session.query(InvestigationReview)
            .filter(InvestigationReview.kind == "appeal", InvestigationReview.status == "resolved")
            .order_by(InvestigationReview.resolved_at.asc()).all())
    latest = {}
    for review in rows:
        latest[review.investigation_id] = review

    items, seen = [], set()
    for review in latest.values():
        if review.reviewer_label not in ("fraud", "legitimate"):
            continue
        inv = review.investigation
        source = inv.inputs[0] if inv.inputs else None
        content = (source.redacted_content if source else None) or ""
        if not content.strip() or inv.type not in ("text", "message", "email", "url"):
            continue
        key = template(content)
        if key in seen:
            continue
        seen.add(key)
        items.append({
            "id": f"r-{inv.public_id}",
            "type": inv.type,
            "label": "fraud" if review.reviewer_label == "fraud" else "benign",
            "kind": inv.classification or "unknown",
            "lang": inv.language or "-",
            "content": content,
            "split": assign_split(content),
            "source": "reviewer_decision",
            "system_level_at_review": review.system_level,
            "config_version_at_review": review.system_config_version,
        })
    return items


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--confirm-consent", action="store_true",
                        help="The operator has decided that reviewed submissions may be used for evaluation.")
    args = parser.parse_args(argv)
    if not args.confirm_consent:
        print("Refusing to export: pass --confirm-consent once the use of reviewed submissions "
              "for evaluation has been approved.", file=sys.stderr)
        return 2

    from truthshield.infra.database import SessionLocal

    session = SessionLocal()
    try:
        items = collect(session)
    finally:
        session.close()
    with args.out.open("w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    splits = {s: sum(1 for i in items if i["split"] == s) for s in ("development", "validation", "test")}
    print(f"{len(items)} reviewed items written to {args.out} {splits}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
