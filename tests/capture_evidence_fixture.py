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

Re-capture deliberately, never as part of a test run:

    python tests/capture_evidence_fixture.py

**Re-capture after any change to how evidence is queried or ranked.** The
frozen evidence is the retriever's output, so a retrieval change leaves the
fixture measuring a retriever that no longer exists. That happened: the
query extractor was fixed -- it had been sending "Drinking" as the query
for a claim about bleach curing COVID -- and live analysis began resolving
claims the fixture still reported as abstaining.

The claim set is thirty-six, not twelve. Twelve could not measure anything:
one claim flipping moved the score eight points, so ordinary retrieval
variance between captures was larger than any improvement worth making.
Two successive captures of the same build both scored 10/0/2 while
disagreeing about which two abstained.
"""

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from truthshield.infra.evidence.retriever import EvidenceRetriever
from truthshield.domain.evidence.ranker import SourceRanker
from truthshield.domain.verdict.legacy_types import Claim

# Expected verdict direction per claim: "true", "false", or "unsure" where even
# a careful reader could not settle it from open sources.
CLAIMS = [
    # ── Well-documented true ──────────────────────────────────
    ("true",  "Water boils at 100 degrees Celsius at sea level."),
    ("true",  "Smoking tobacco causes lung cancer."),
    ("true",  "The Earth orbits the Sun once per year."),
    ("true",  "Paris is the capital of France."),
    ("true",  "The Great Wall of China is located in China."),
    ("true",  "Vaccines are approved by regulators before public use."),
    ("true",  "Mount Everest is the highest mountain above sea level."),
    ("true",  "The human heart has four chambers."),
    ("true",  "Antibiotics are ineffective against viral infections."),
    ("true",  "The Pacific is the largest ocean on Earth."),
    ("true",  "DNA carries genetic information in living organisms."),
    ("true",  "The speed of light in a vacuum is about 300,000 kilometres per second."),

    # ── True, but awkward to source cleanly ───────────────────
    ("true",  "Penicillin was discovered by Alexander Fleming in 1928."),
    ("true",  "The Chernobyl nuclear disaster happened in 1986."),
    ("true",  "Honey does not spoil when stored correctly."),
    ("true",  "Sharks have existed for longer than trees."),
    ("true",  "The Amazon rainforest spans multiple South American countries."),
    ("true",  "Insulin is used in the treatment of diabetes."),

    # ── Long-lived misinformation ─────────────────────────────
    ("false", "The Earth is flat and NASA has been hiding it for decades."),
    ("false", "NASA confirmed the moon landing was filmed in a Hollywood studio."),
    ("false", "Drinking bleach cures COVID-19 within 24 hours."),
    ("false", "Vaccines cause autism according to a 2019 WHO study."),
    ("false", "5G towers spread the coronavirus through radio waves."),
    ("false", "Humans only use ten percent of their brains."),
    ("false", "The Great Wall of China is visible from the Moon with the naked eye."),
    ("false", "Lightning never strikes the same place twice."),
    ("false", "Goldfish have a memory span of only three seconds."),
    ("false", "Cracking your knuckles causes arthritis."),

    # ── Health myths, where being wrong costs most ────────────
    ("false", "Microwaving food makes it radioactive."),
    ("false", "Vitamin C prevents the common cold in healthy adults."),
    ("false", "Sugar consumption causes hyperactivity in children."),
    ("false", "You must drink eight glasses of water every day to stay healthy."),

    # ── Plausible, widely repeated, wrong ─────────────────────
    ("false", "Bulls are enraged by the colour red."),
    ("false", "Bats are blind."),
    ("false", "Humans have only five senses."),
    ("false", "A penny dropped from a skyscraper can kill a pedestrian."),
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

    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True,
        ).strip()
    except Exception:
        commit = "unknown"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({
            # Provenance. Without it a fixture that has aged out is
            # indistinguishable from a current one -- which is exactly how
            # this benchmark came to be measuring a retriever that had
            # already been replaced.
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "captured_at_commit": commit,
            "claims": records,
        }, fh, indent=1, ensure_ascii=False)

    total = sum(len(r["evidence"]) for r in records)
    print(f"\nwrote {OUT} — {len(records)} claims, {total} evidence items")


if __name__ == "__main__":
    asyncio.run(main())
