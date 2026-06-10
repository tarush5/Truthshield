"""Quick end-to-end test for the TruthShield pipeline."""
import sys, os, asyncio, time

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(".")))

from backend.pipeline.decision_pipeline import DecisionPipeline
from backend.models.schemas import AnalyzeRequest


async def run_test_pipeline():
    pipeline = DecisionPipeline()

    test_claims = [
        "The Earth is definitively flat and NASA admits it.",
        "COVID-19 vaccines contain microchips for tracking people.",
        "India successfully landed on the Moon's south pole in 2023.",
    ]

    for claim_text in test_claims:
        print(f"\n{'='*70}")
        print(f"CLAIM: {claim_text}")
        print(f"{'='*70}")

        t0 = time.time()
        req = AnalyzeRequest(text=claim_text, lang="en")
        report = await pipeline.execute(text=req.text, lang=req.lang.value)
        elapsed = time.time() - t0

        v = report.credibility.verdict
        verdict_str = v.value if hasattr(v, "value") else v
        print(f"  Verdict     : {verdict_str}")
        print(f"  Trust Score : {report.credibility.trust_score}/100")
        print(f"  Time        : {elapsed:.1f}s")
        print(f"  Claims      : {len(report.claims)}")

        for c in report.claims:
            cv = c.verdict
            cv_str = cv.value if hasattr(cv, "value") else cv
            print(f"    -> {cv_str} (conf={c.confidence:.2f}): {c.claim.text[:80]}")
            print(f"       Reason: {c.reasoning[:120]}")
            for e in c.evidence[:3]:
                snippet = (getattr(e, "snippet", "") or "")[:60]
                print(f"         - {snippet}...")
        print()


asyncio.run(run_test_pipeline())
