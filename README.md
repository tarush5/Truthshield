# TruthShield

Misinformation analysis: extract the checkable claims from a piece of content,
find evidence, work out which way each source cuts, and report a verdict —
**along with everything that could not be checked**.

That last part is the design constraint. A fact-checking tool that confidently
mislabels what it could not establish is worse than one that says so.

---

## What it does

Submit text, a link, or a file. You get back:

- a **verdict** from an eight-value vocabulary, including
  `INSUFFICIENT EVIDENCE` as a first-class outcome;
- a **trust score** (0–100) whose four components are broken out;
- **each claim** with the sources behind it and which way each one cut;
- **each source** with its publisher, credibility tier and stance;
- an explicit list of **limitations** — checks that could not run, and why.

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Authorization: Bearer $TOKEN" \
  -F "text=Drinking bleach cures COVID-19 within 24 hours."
```

```json
{
  "verdict": "LIKELY FALSE",
  "trust_score": 44,
  "fake_probability": 55,
  "confidence_band": "MODERATE",
  "breakdown": {
    "fact_match": 30.7,
    "source_credibility": 79.5,
    "evidence_strength": 56.0,
    "manipulation_risk": 50.0
  },
  "reasons": ["Authoritative source(s) addressed this claim (www.who.int)",
              "Contradicted by 4 sources"],
  "limitations": []
}
```

`manipulation_risk: 50` means *not assessed* — the submission was text, so
there was no image or audio to check. It does not mean "50% risky".

---

## Running it

### Docker (everything)

```bash
export JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
docker compose up --build
```

Postgres, Redis, the API, a Celery worker and the web app. Migrations run
before the API accepts traffic.

| Service | URL |
|---|---|
| Web | http://localhost:5173 |
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |

### Locally, without Docker

```bash
python -m venv .venv && .venv/Scripts/activate      # or source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env                                 # then edit it
alembic upgrade head
uvicorn truthshield.main:app --reload --port 8000

cd frontend && npm install && npm run dev
```

SQLite and an in-process cache are allowed outside production, so this works
with nothing else running. Both are refused when `APP_ENV=production`.

### Optional: local ML detectors

```bash
pip install -r requirements-ml.txt    # ~2 GB
# then set ENABLE_ML_DETECTORS=true
```

Without them the image, video and audio detectors report `unavailable` and the
report says so. They never report a clean result for a check that did not run.

`GET /api/v1/health` lists what is actually available:

```json
{"capabilities": {"torch": true, "opencv": true, "tesseract_ocr": false, ...}}
```

`tesseract_ocr` needs the Tesseract **binary**, not just the Python package —
importing `pytesseract` succeeds on a machine with no OCR installed.

---

## Architecture

```
truthshield/
├── api/          HTTP layer — routing and serialization only
├── domain/       Pure logic, no I/O
│   ├── credibility.py    source scoring
│   ├── verdict/          claim extraction, stance, verdicts
│   ├── evidence/         ranking
│   ├── scoring/          trust score and verdict fusion
│   └── types.py          the vocabulary everything shares
├── detectors/    manipulation checks, each reporting whether it ran
├── infra/        database, cache, Celery, evidence retrieval
├── security/     SSRF guard
└── services/     orchestration — pipeline, analysis, auth
```

`domain/` has no database, no HTTP and no framework, so the analysis logic can
be tested and reasoned about without a request in flight.

---

## Testing

```bash
pytest tests/          # fast, offline, deterministic
```

| Suite | What it pins |
|---|---|
| `test_api.py` | Auth, access control, validation — through the real app |
| `test_scoring.py` | That a report never claims more than it checked; verdict accuracy |
| `test_security.py` | SSRF, fail-closed config, token verification, password handling |

### Why the evidence is frozen

Verdict accuracy used to be measured against live search, which makes the
number meaningless for judging a change: the same build scored 6/8 and 2/8 on
consecutive runs purely on what the web returned that minute — one of those
runs had DuckDuckGo timing out entirely.

`tests/fixtures/evidence_fixture.json` holds real retrieved evidence for 12
claims, captured once. Two properties are asserted separately:

- **Precision** — no claim may be decided in the wrong direction. Currently
  **0 wrong**.
- **Coverage** — the engine must still commit on most claims, since abstaining
  everywhere would satisfy precision while being useless. Currently **9/12**.

Refresh the fixture deliberately, never inside a test run:

```bash
python tests/capture_evidence_fixture.py
```

---

## Configuration

Everything is environment variables; see `.env.example`. The settings that
matter:

| Variable | Default | Notes |
|---|---|---|
| `APP_ENV` | `production` | Defaults to the strict value. A deployment that forgets it fails closed. |
| `JWT_SECRET_KEY` | *(none)* | **Startup fails** in production without a real one. |
| `DATABASE_URL` | Postgres | SQLite is refused in production. |
| `CORS_ORIGINS` | `localhost:5173` | Exact origins. `*` is rejected. |
| `ENABLE_ML_DETECTORS` | `false` | Local inference; needs `requirements-ml.txt`. |

Misconfiguration raises at startup rather than surfacing later as a 500.

---

## Known limitations

- **Evidence quality is bounded by search.** With no API keys configured it
  falls back to DuckDuckGo and Wikipedia, which is why three of the twelve
  benchmark claims abstain — the debunks exist but are headlined as questions
  with no body text in the snippet.
- **The detectors are heuristics, not trained classifiers.** They measure real
  signals and say which method produced a result, but a fine-tuned deepfake
  model would be better and is not shipped.
- **OTP codes are logged, not emailed.** Wiring an email provider is the
  remaining step for passwordless sign-in in production.
- **Two npm advisories remain**, both needing react-router 7 — a breaking major
  left for a deliberate upgrade.

---

## License

MIT.
