# TruthShield 2.0

**Verify before you trust.** A multimodal fraud, misinformation and
digital-trust investigation platform. Submit suspicious content and get back
an evidence-backed, explainable investigation, not a bare "scam: 95%".

```
Risk 99/100 · CRITICAL · confidence 0.85 (capped: heuristics only)
Potential phishing. Main drivers:
  +37  Bank impersonation            Language · Heuristic   "kyc updat…"
  +27  Payment or OTP request        Language · Heuristic   "share the otp"
  +11  Time pressure                 Language · Heuristic   "turant"
  +10  Brand name used in a subdomain  URL · Heuristic      secure.sbi.kyc-verify-update.xyz
Not assessed: reputation (no threat-intel provider), behavioral, document/media
Uncertain: domain age not checked (no WHOIS) · page not fetched · …
```

Every result keeps five kinds of information apart: **verified input facts**
(SHA-256, verbatim excerpts), **retrieved sources**, **heuristic signals**,
**model predictions** and **LLM interpretation**. It also states its
**uncertainty**: what could not be checked is listed and never implied clean.

---

## What works today (Phase 1)

| | |
|---|---|
| **Investigations** | `TS-2026-000042` IDs · 12 audited pipeline stages · SHA-256 on every input · live progress |
| **Text engine** | English / Hindi / Tamil detection · entities (URLs, phones, UPI, amounts, dates, organisations) · claims · intent · scam categories (Hinglish-aware) · manipulation tactics · prompt-injection flag |
| **URL engine** | Typosquats · brand mismatch · structural phishing rules · feature vector (entropy, digit ratio, …) · SSRF-guarded page inspection (forms, redirects, scripts), never executing JS |
| **Evidence engine** | Claim verification against retrieved sources: `SUPPORTED` / `CONTRADICTED` / `MIXED` / `INSUFFICIENT_EVIDENCE`, never forced |
| **Risk engine** | Configurable weights · noisy-OR across signal families · exact per-signal attribution (the breakdown sums to the score) · confidence as its own axis |
| **Security** | JWT + rotating refresh tokens with reuse detection · USER/ANALYST/ADMIN · lockout · audit log · rate limits · error envelope with request IDs |
| **Frontend** | React 19 + TypeScript: landing page, dashboard (real aggregates), investigate workspace, 9-tab result page, history, URL intelligence |

Image, audio, video, PDF/OCR, transactions, pgvector RAG, agents and the
knowledge graph are **planned, not faked**. The UI labels each one with its
phase. See [docs/ROADMAP.md](docs/ROADMAP.md).

## Run it

### Docker

```bash
export JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
docker compose up --build
```

| Service | URL |
|---|---|
| Web | http://localhost:5173 |
| API | http://localhost:8000 · docs at `/docs` outside production |

### Locally

```bash
python -m venv .venv && .venv/Scripts/activate      # or: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                                 # APP_ENV=development, SQLite
alembic upgrade head
uvicorn truthshield.main:app --reload --port 8000

cd frontend && npm install && npm run dev            # http://localhost:5173
```

Set `BOOTSTRAP_ADMIN_EMAILS=you@example.com` to become an administrator on
sign-up. Set `OFFLINE_MODE=true` to run with no outbound requests at all.
The synthetic demos work either way.

## Test

```bash
pytest tests/ -q            # backend: 409 tests, offline and deterministic
ruff check truthshield tests
cd frontend && npm run typecheck && npm test && npm run build
```

CI runs all of this on real Postgres and Redis, applies migrations up, down
and up again, fails on model/migration drift (`alembic check`), and enforces a
165 kB gzipped budget on the initial frontend payload.

## Documentation

[Architecture](ARCHITECTURE.md) · [Migration from 1.x](docs/MIGRATION.md) ·
[Database](docs/DATABASE.md) · [API](docs/API.md) ·
[AI services](docs/AI_SERVICES.md) · [Workers](docs/WORKERS.md) ·
[Frontend](docs/FRONTEND.md) · [Roadmap & acceptance status](docs/ROADMAP.md)

## Known limitations

- **Evidence recall depends on search keys.** Without `GOOGLE_CSE_*`,
  `BRAVE_API_KEY` or `SERPAPI_API_KEY`, retrieval runs on DuckDuckGo,
  Wikipedia and RSS, and many claims honestly end as
  `INSUFFICIENT_EVIDENCE`. `GET /api/v1/system/health` reports `degraded`
  in that state.
- **Phase 1 detectors are rule-based.** No trained-model metrics are shown,
  because none have been measured. Confidence is capped accordingly.
- **Reputation, WHOIS and certificate checks** need providers that are not
  configured yet. Every URL result lists them as unchecked.

## License

MIT.
