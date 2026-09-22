"""
Capture real retrieved evidence into a fixture, once, for offline scoring.

Why this exists
---------------
The end-to-end benchmark hits live search, so the evidence behind a claim
changes between runs and a verdict can flip without a line of code changing.
Two consecutive runs of the same build scored 6/8 and 2/8 purely on what the
web returned that minute, which makes it useless for judging whether a change
to stance detection helped or hurt.

This script does the network part once and writes the result to
`tests/fixtures/evidence_fixture.json`. `test_verdict_accuracy.py` then scores
the verdict engine against that frozen evidence, so a change in the score is a
change in the code.

Re-capture deliberately (the web moves, and the fixture should be refreshed
every so often), never as part of a test run:

    python tests/capture_evidence_fixture.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.factcheck.evidence_retriever import EvidenceRetriever
from backend.factcheck.source_ranker import SourceRanker
from backend.models.schemas import Claim

# Expected verdict direction per claim: "true", "false", or "unsure" where even
# a careful reader could not settle it from open sources.
CLAIMS = [
    ("true",  "Water boils at 100 degrees Celsius at sea level."),
    ("true",  "Smoking tobacco causes lung cancer."),
    ("true",  "The Earth orbits the Sun once per year."),
    ("true",  "Paris is the capital of France."),
    ("true",  "The Great Wall of China is located in China."),
    ("true",  "Vaccines are approved by regulators before public use."),
    ("false", "The Earth is flat and NASA has been hiding it for decades."),
    ("false", "NASA confirmed the moon landing was filmed in a Hollywood studio."),
    ("false", "Drinking bleach cures COVID-19 within 24 hours."),
    ("false", "Vaccines cause autism according to a 2019 WHO study."),
    ("false", "5G towers spread the coronavirus through radio waves."),
    ("false", "Humans only use ten percent of their brains."),
]

OUT = Path(__file__).resolve().parent / "fixtures" / "evidence_fixture.json"


async def main():
    retriever = EvidenceRetriever()
    ranker = SourceRanker()
    records = []

    for expected, text in CLAIMS:
        claim = Claim(text=text)
        evidence = await retriever.retrieve(claim)
        evidence = ranker.filter_disinfo(ranker.rank_evidence(evidence))
        records.append({
            "expected": expected,
            "claim": text,
            "evidence": [
                {
                    "title": ev.title,
                    "url": ev.url,
                    "snippet": ev.snippet,
                    "source_score": ev.source_score,
                }
                for ev in evidence
            ],
        })
        print(f"{expected:<6} {len(records[-1]['evidence']):>3} items  {text[:56]}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"claims": records}, fh, indent=1, ensure_ascii=False)

    total = sum(len(r["evidence"]) for r in records)
    print(f"\nwrote {OUT} — {len(records)} claims, {total} evidence items")


if __name__ == "__main__":
    asyncio.run(main())
