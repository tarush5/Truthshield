# Roadmap and acceptance status

Status as of **1 October 2026**, branch `v2/phase-1`.
Legend: ✅ done and tested · 🟡 partial (what exists is stated) · ⬜ not started.

## Phase 1 — foundation (this branch)

| Item | Status | Evidence |
|---|---|---|
| Repository audit and migration plan | ✅ | [MIGRATION.md](MIGRATION.md) |
| Architecture, database, API, AI-service, worker and frontend design docs | ✅ | `ARCHITECTURE.md`, `docs/*.md` |
| Schema: investigations, inputs, events, risk factors, predictions, refresh tokens, roles | ✅ | migration `7a1c2e9d4b10`; CI runs up → down → up and `alembic check` |
| Auth: refresh rotation with reuse detection, logout, USER/ANALYST/ADMIN, lockout, audit log | ✅ | `tests/test_v2_auth.py` |
| Investigation framework: `TS-YYYY-NNNNNN` ids, 12 audited stages, SHA-256, immutable inputs | ✅ | `tests/test_v2_investigations.py` |
| Text engine: language (en/hi/ta), normalisation, entities, claims, intents, scam/manipulation, prompt-injection flag | ✅ | `tests/test_v2_engines.py` |
| URL engine: feature vector, 1.x structure rules, typosquat, brand mismatch, SSRF-guarded page inspection, cache | ✅ | `tests/test_v2_engines.py` |
| Evidence engine over the 1.x retrieval stack, with credibility guard and claim-quality gate | 🟡 | Works end to end. Recall is bounded by the keyless search fallbacks (see README). pgvector RAG is Phase 2 |
| Central risk engine: configurable weights, noisy-OR, exact attribution, separate confidence | ✅ | `tests/test_v2_risk.py` |
| Deterministic explanation, uncertainty, safety guidance | ✅ | |
| Executors: inline / background / Celery; 503 plus FAILED record when the broker is down | ✅ | `TestExecutors` |
| Standard error envelope (1.x-compatible) | ✅ | |
| Frontend 2.0: design system, landing, auth, dashboard, investigate, result (9 tabs), history, URL intelligence, settings, module pages, 1.x report links | ✅ | typecheck, 16 unit tests, build, browser run |
| JSON and CSV export (formula-safe) | ✅ | |
| Lint, type check and bundle budget in CI | ✅ | `.github/workflows/ci.yml` |

**Measured on the dev machine** (SQLite, no search API keys; single runs,
not a benchmark):

| Input | End-to-end |
|---|---|
| Phishing SMS (demo) | 0.42 s |
| Typosquat URL (demo) | 0.15 s |
| Health-misinformation claim, with live evidence retrieval | 4.1–5.2 s |

## Phase 2 — evidence, documents, providers

| Item | Status | Evidence |
|---|---|---|
| Provider abstractions: LLM (Anthropic SDK, Gemini, none), search, embeddings, OCR; resilience (retry, backoff, circuit breaker) | ✅ | `tests/test_v2_rag.py::TestProviders` |
| Evidence store on pgvector: HNSW cosine + GIN full-text, RRF fusion, filters, query expansion, reranking | ✅ | `tests/test_v2_rag.py`, `tests/test_v2_postgres.py` (CI) |
| Source registry with admin curation; claim records and claim search | ✅ | `tests/test_v2_evidence_api.py` |
| Evidence engine on RAG; deterministic adjudication (1.x LLM verdict paths off); credibility guard | ✅ | `tests/test_v2_engines.py::TestEvidenceEngine` |
| Grounded LLM interpretation: findings-only prompt, citation validation, refusal handling, token usage recorded | ✅ | `tests/test_v2_interpret.py` (fake provider; no live LLM call made in tests) |
| Secure file intake: magic-byte sniffing, size cap, SHA-256, content-addressed storage, temp cleanup, deletion | ✅ | `tests/test_v2_documents.py::TestIntake` |
| PDF engine: structure (active content, incremental saves), metadata, fields, consistency, OCR for scanned pages | ✅ | `tests/test_v2_documents.py` |
| Image engine: decode guard, EXIF, OCR with word boxes | ✅ OCR needs the Tesseract binary (in Docker and CI; not on this dev machine) | `tests/test_v2_ocr_real.py` (CI) |
| Frontend: file upload, Document/Image result views, OCR overlay, Evidence page, Document Forensics page | ✅ | type check, build, browser run |
| Table extraction from PDFs | ⬜ | moved to Phase 3 |
| Retrieval evaluation (Recall@K, MRR, NDCG) of the store-first path | ⬜ | Phase 6 |

## Phases 3–8

| Phase | Scope | Status |
|---|---|---|
| 2 | pgvector hybrid RAG with reranking, source registry, claim workspace, PDF + OCR, LLM and search provider abstractions, grounded LLM interpretation | ✅ (see above) |
| 3 | S3-compatible storage backend, image forensics (ELA, copy-move), image synthetic-media, audio, chunked video, PDF tables, Celery media queue | ⬜ |
| 4 | Transaction feature pipeline, Isolation Forest, transaction graph, QR decoding | ⬜ |
| 5 | Knowledge graph tables, multimodal fusion, LangGraph agents with tool allowlists, threat-intel views | ⬜ |
| 6 | PDF reports, analytics (feedback, FP/FN), MLflow model registry, feedback capture | ⬜ |
| 7 | OpenTelemetry, Prometheus, Grafana, per-role rate limits, cost tracking, retention purge, reputation/WHOIS providers | ⬜ |
| 8 | E2E tests (Playwright), deploy stages in CI, remaining documentation (SECURITY, ML, RAG, AGENTS, DEPLOYMENT, TESTING, CONTRIBUTING) | ⬜ |

## Master acceptance checklist (spec §98)

| Criterion | Status |
|---|---|
| Existing functionality preserved | ✅ All 1.x endpoints kept; 300 of 300 1.x tests still pass (2 updated for the `.js` → `.ts` rename); 1.x report and share links render in 2.0 |
| User authentication | ✅ |
| Investigation creation | ✅ |
| Text analysis | ✅ |
| URL analysis | ✅ |
| Claim extraction | ✅ |
| Risk engine | ✅ |
| Explainability | ✅ |
| Investigation timeline | ✅ |
| Evidence provenance | 🟡 Signal → excerpt and claim → source → passage are shown. A graph view comes in Phase 5 |
| Reports | 🟡 JSON/CSV. PDF in Phase 6 |
| PDF analysis, OCR | ✅ OCR requires Tesseract (installed in Docker/CI) |
| RAG retrieval, pgvector | ✅ |
| Dashboard uses real data | ✅ |
| Security controls | 🟡 Auth, RBAC, SSRF, rate limits, lockout, audit, CSV-injection and unsafe-href guards. Upload hardening in Phase 3 |
| Prompt-injection protections | 🟡 Detection and isolation (no LLM in the decision path). Agent sandboxing in Phase 5 |
| SSRF protections | ✅ |
| Rate limiting | ✅ Global, auth and analysis limits. Per-role limits in Phase 7 |
| Background workers | ✅ Celery path wired and tested (eager). Media queues in Phase 3 |
| PostgreSQL | ✅ Migrations run against Postgres in CI |
| Redis | ✅ Cache, OTP, lockout counters, Celery broker (with a declared degraded fallback) |
| Tests pass | ✅ 477 backend (+3 Postgres/OCR tests that run in CI), 16 frontend |
| Demo mode without credentials | ✅ `OFFLINE_MODE=true` plus synthetic demos through the real pipeline |
| No fake metrics or fabricated evidence | ✅ No model metrics are displayed; landing-page statistics come from `/system/health` |
| Image forensics, audio, video, deepfake, fraud ML, multi-agent, knowledge graph, model registry, feedback, monitoring, CI deploy | ⬜ Phases 3–8 |
