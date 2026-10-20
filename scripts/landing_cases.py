"""
Regenerate the example cases shown on the landing page.

    python scripts/landing_cases.py

Each case is a synthetic demo sample (truthshield/investigations/demo.py) run
offline through the real text, URL and risk engines. The landing page shows
these numbers, so they must come from the engines, never be typed by hand;
tests/test_v2_landing_cases.py fails when the file drifts from the engines.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("JWT_SECRET_KEY", "x" * 64)
os.environ.setdefault("DATABASE_URL", "sqlite:///./truthshield_test_v2.db")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:1")
os.environ["OFFLINE_MODE"] = "true"

OUT = ROOT / "frontend" / "src" / "components" / "landing" / "cases.json"

# demo id -> how the landing page presents it. Colours are the page palette.
PRESENTATION = [
    ("phishing-sms", "kyc phishing", "& a lookalike link", "orange"),
    ("suspicious-url", "fake sign-in", "& a typosquatted domain", "amber"),
    ("phishing-email", "invoice email", "& a spoofed sender", "green"),
    ("prize-scam", "prize scam", "& a reward to claim", "pink"),
    ("prompt-injection", "parcel scam", "& orders for the ai", "blue"),
    ("benign-message", "just a message", "& nothing to flag", "yellow"),
]


def run(sample: dict) -> dict:
    import hashlib

    from truthshield.investigations import explain
    from truthshield.investigations.engines import analysis_engines
    from truthshield.investigations.risk import RiskEngine
    from truthshield.investigations.types import EngineStatus, InvestigationContext, InvestigationType

    kind = InvestigationType(sample["type"])
    content = sample["content"]
    ctx = InvestigationContext(
        investigation_id="landing", type=kind, content=content, text=content,
        input_sha256=hashlib.sha256(content.encode()).hexdigest(), allow_page_fetch=False,
    )
    text_engine, url_engine = analysis_engines()
    text = text_engine.run(ctx)
    ctx.artifacts.update(text.artifacts)
    if text.status is EngineStatus.NOT_APPLICABLE and kind is InvestigationType.URL:
        ctx.urls = [content.strip()]
    url = url_engine.run(ctx)
    engines = [text, url]
    assessed = {f for e, f in (("text", "nlp"), ("url", "url")) for r in engines if r.engine == e and r.status is EngineStatus.OK}
    assessment = RiskEngine().assess([s for e in engines for s in e.signals], engines, assessed)
    classification, _ = explain.classify(assessment, engines)
    signals = [c for c in assessment.contributions if c.points > 0][:3]
    return {
        "score": assessment.score,
        "level": assessment.level,
        "classification": classification,
        "signals": [{"title": c.title, "points": c.points, "evidence": (c.evidence or "")[:60]} for c in signals],
    }


def build() -> list:
    from truthshield.investigations.demo import SAMPLES

    by_id = {s["id"]: s for s in SAMPLES}
    cases = []
    for demo_id, title, sub, colour in PRESENTATION:
        sample = by_id[demo_id]
        cases.append({
            "id": demo_id, "title": title, "sub": sub, "colour": colour,
            "type": sample["type"], "content": sample["content"], **run(sample),
        })
    return cases


if __name__ == "__main__":
    OUT.write_text(json.dumps(build(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
