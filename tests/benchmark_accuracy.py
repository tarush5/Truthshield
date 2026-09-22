"""
End-to-end accuracy benchmark against a running backend.

Not a pytest test: it needs a live server on :8000 and real network access, so
its results move with whatever the web returns. Run it by hand when changing
stance detection or the aggregator, to check a change that helps one direction
has not simply made the engine credulous in the other.

    uvicorn backend.main:app --port 8000     # in one shell
    python tests/benchmark_accuracy.py       # in another
"""
import json, sys, urllib.request, urllib.parse

CASES = [
    ("TRUE",  "Water boils at 100 degrees Celsius at sea level."),
    ("TRUE",  "Smoking tobacco causes lung cancer."),
    ("TRUE",  "The Earth orbits the Sun once per year."),
    ("TRUE",  "Paris is the capital of France."),
    ("FALSE", "The Earth is flat and NASA has been hiding it for decades."),
    ("FALSE", "NASA confirmed the moon landing was filmed in a Hollywood studio."),
    ("FALSE", "Drinking bleach cures COVID-19 within 24 hours."),
    ("FALSE", "Vaccines cause autism according to a 2019 WHO study."),
]

TRUEISH  = {"TRUE", "VERIFIED", "LIKELY TRUE", "PARTIALLY TRUE"}
FALSEISH = {"FALSE", "LIKELY FALSE", "MISLEADING"}

rows, correct, wrong, unsure = [], 0, 0, 0
for expect, text in CASES:
    data = urllib.parse.urlencode({"text": text, "lang": "en"}).encode()
    req = urllib.request.Request("http://127.0.0.1:8000/api/v1/analyze", data=data)
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            d = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        rows.append((expect, "ERROR", 0, text, str(e)[:40])); wrong += 1; continue
    v = d["credibility"]["verdict"]; ts = d["credibility"]["trust_score"]
    if (expect == "TRUE" and v in TRUEISH) or (expect == "FALSE" and v in FALSEISH):
        mark, correct = "OK ", correct + 1
    elif v in TRUEISH or v in FALSEISH:
        mark, wrong = "BAD", wrong + 1
    else:
        mark, unsure = "..?", unsure + 1
    rows.append((expect, v, ts, text, mark))

print(f"{'want':<6} {'got':<20} {'trust':>5}  claim")
print("-" * 92)
for expect, v, ts, text, mark in rows:
    print(f"{mark} {expect:<5} {v:<20} {ts:>5}  {text[:52]}")
print("-" * 92)
print(f"correct={correct}  wrong={wrong}  unsure={unsure}  of {len(CASES)}")
