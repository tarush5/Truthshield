# TruthShield 1.x → 2.0 Migration Plan

Status: **Phase 1 in progress** on branch `v2/phase-1`.
Audit performed against `main @ 4bac1bd` (26 Sep 2026). Baseline: **300 backend tests passing**.

This document records what the 1.x codebase actually contains, what is kept,
what is replaced, and in what order. It is written before the code changes so
the changes can be reviewed against it.

---

## 1. Audit of the existing system

### 1.1 What exists and works

| Area | Where | Assessment |
|---|---|---|
| Configuration | `truthshield/settings.py` | **Keep.** Fails closed (APP_ENV defaults to production, placeholder JWT secrets and SQLite are refused in production), legible startup errors. |
| Auth | `services/auth.py`, `api/deps.py` | **Keep & extend.** PBKDF2-SHA256 (240k), constant-time compares, no guest fallback, symmetric-only JWT, hashed API keys, Redis OTP with attempt limits. Missing: refresh tokens, logout, system roles, lockout. |
| SSRF guard | `security/url_guard.py` | **Keep.** Scheme allowlist, resolves every address, re-validates each redirect hop, response size cap. Reused by the 2.0 URL engine. |
| Fact-check pipeline | `services/pipeline.py`, `domain/verdict/*`, `infra/evidence/*`, `ml/nli.py` | **Keep; becomes the Evidence Engine.** Claim extraction, multi-provider retrieval, credibility ranking, NLI stance, frozen-evidence benchmark (0 wrong / 9 of 12 decided). |
| Fraud platform | `fraud/*` | **Keep; becomes the heuristic core of the Text and URL engines.** Auditable `FraudFinding` contract (indicators, limitations, separate risk/confidence), plugin registry, Hinglish-aware scam patterns, URL structure rules, email header rules, PII redaction, per-category safety guidance. |
| Media detectors | `detectors/registry.py` | Keep for Phase 3. Report `unavailable` honestly when ML extras are absent. |
| RAG | `domain/rag/*` | Keep; rebuilt on pgvector in Phase 2. Citation verification against retrieved sources is already implemented. |
| Streaming | `api/stream.py` | Keep (SSE for fact-check). |
| Sharing | `api/sharing.py` | Keep. Revocable, unguessable share tokens. |
| Analytics | `domain/analytics.py`, `api/insights.py` | Keep; extended to investigations. |
| Persistence | `infra/models.py`, Alembic | **Keep.** Alembic owns the schema; FKs with explicit `ondelete`. |
| Infra | `docker-compose.yml`, `Dockerfile`, `render.yaml`, CI | Keep. CI runs tests against real Postgres + Redis and checks migrations apply from empty. |

### 1.2 Technical debt

1. **`ARCHITECTURE.md` described a system that does not exist** (social-media monitors, an XLM-RoBERTa classifier, a Claude verdict engine, a WhatsApp bot). Replaced in 2.0.
2. **Two disconnected analysis paths.** `/analyze` (fact-check) persists a report; `/fraud/analyze` persists nothing. There is no shared investigation record, no ID a user can quote, and no per-stage timeline.
3. **Giant modules.** `domain/verdict/engine.py` (1,454 lines) and `infra/evidence/retriever.py` (1,451 lines). They carry measured fixes, so they are wrapped rather than rewritten now, then split during the Phase 2 RAG rebuild.
4. **Dual type systems** (`legacy_types.py` + `adapters.py`) left over from the port.
5. **Dependency drift.** `duckduckgo_search` has been renamed to `ddgs` (a warning on every search). `python-jose` calls the deprecated `utcnow()`.
6. **Frontend:** untyped JSX, hand-rolled data fetching, two npm advisories that need react-router 7.

### 1.3 Broken or missing functionality

| Finding | Evidence | Fix |
|---|---|---|
| `audit_logs` table is **never written** | No `AuditLog(` constructor outside the model | Phase 1: audit helper, used for login, investigation create/delete, and role changes |
| `RATE_LIMIT_AUTH` is **defined but never applied**; `rate_limit_key` is unused | grep | Phase 1: auth routes get the stricter limit, plus a per-email lockout |
| No refresh tokens, no logout, no system roles | `services/auth.py` | Phase 1 |
| Fraud results are not stored | `api/fraud.py` | Phase 1: investigations persist everything |
| No input hashing or immutable input record | — | Phase 1: SHA-256 on every input; `investigation_inputs` rows are never updated |

### 1.4 Performance bottlenecks

The memory issue called out for 1.x (reading whole uploads into memory) is **already fixed**: uploads stream in 1 MB chunks under a running cap. What remains:

- **Uploaded files and extracted frames are never deleted** (`.uploads/`, `.uploads/frames/`), so disk use grows without bound. Fixed in Phase 3, when file ingestion moves into the worker with guaranteed cleanup.
- Video frame extraction seeks frame-by-frame in the API process when run synchronously. Phase 3 moves all media to Celery workers.
- Evidence retrieval runs about 1.5 s median per claim and fans out across providers. Bounded by `MAX_CLAIMS_PER_SUBMISSION` and timeouts, and cached per claim in Phase 2.

### 1.5 Security findings

| Finding | Severity | Phase |
|---|---|---|
| Auth endpoints limited only by the global 60/min per-IP limit | Medium | 1 |
| No account lockout on repeated failed sign-ins | Medium | 1 |
| Access tokens cannot be revoked (no logout) | Medium | 1 (refresh tokens are revocable; access tokens stay short-lived) |
| File type decided by extension only, with no content sniffing | Medium | 3 (with file ingestion) |
| Tokens stored in `localStorage` (XSS exposure) | Low–Medium | Documented trade-off; revisit with same-site cookie deployment |
| Unhandled errors already return only a request ID; SSRF, CORS and secrets are handled well | — | — |

---

## 2. Migration strategy

**Principle: wrap, don't rewrite, anything that carries measured behaviour.**
The verdict engine, retriever and fraud detectors each encode fixes found by
running against real evidence. 2.0 composes them behind new interfaces rather
than retyping them.

### 2.1 Backend

The Python package stays `truthshield/`, so imports, the Dockerfile, the
Render blueprint and all 300 tests keep working. The 2.0 structure in the
master spec (`backend/`, `ai-services/`, …) is mapped onto the package:

| 2.0 spec location | Implemented at |
|---|---|
| `backend/app/api` | `truthshield/api/` |
| `backend/app/core` | `truthshield/settings.py`, `truthshield/api/errors.py` |
| `backend/app/models` | `truthshield/infra/models.py` |
| `backend/app/services` | `truthshield/services/`, `truthshield/investigations/service.py` |
| `backend/app/security` | `truthshield/security/` |
| `ai-services/nlp` | `truthshield/investigations/nlp/`, `truthshield/investigations/engines/text.py` |
| `ai-services/risk` | `truthshield/investigations/risk.py` |
| `ai-services/retrieval` | `truthshield/investigations/engines/evidence.py` → `infra/evidence/` |
| `ai-services/vision`, `audio`, `video` | Phase 3 (`truthshield/investigations/engines/`) |
| `workers/` | `truthshield/infra/celery_app.py` (+ `investigations` tasks) |

Moving the package into `backend/app/` is purely cosmetic and would break
every import. It is deferred until there is a second deployable Python
service, which is the point at which the split actually buys something.

### 2.2 API compatibility

- All 1.x endpoints stay (`/analyze`, `/reports`, `/fraud/*`, `/insights/*`, `/shared/*`).
- 2.0 adds `/investigations`, `/analyze/{text,url,message,email}`, `/dashboard/summary`, `/system/health`, `/engines`, `/demo/samples`, `/auth/refresh`, `/auth/logout` and `/admin/users`.
- Error responses gain a structured `error` object **alongside** the existing `detail` field, so 1.x clients keep working.
- `TokenResponse` gains `refresh_token` and `user.role`. Both are additive.

### 2.3 Frontend

The 1.x JSX app is retired and replaced by a new TypeScript app in
`frontend/`. Existing public share links (`/shared/:token`) and 1.x reports
(`/report/:id`) are rendered by a read-only legacy report view in the new
app, so no link that has been handed out stops working. Live fact-check
streaming (1.x `/analyze/stream`) returns in the 2.0 UI with the Phase 2
evidence workspace; the endpoint itself is unchanged.

### 2.4 Data

Additive Alembic migrations only. No existing table is dropped or rewritten.
1.x reports remain readable and remain in history.

---

## 3. Phase plan

The phase contents follow §95 of the master spec. Status is tracked in
[`ROADMAP.md`](ROADMAP.md).

| Phase | Scope |
|---|---|
| **1** | Architecture docs, DB schema, auth (refresh, roles, lockout, audit), investigation framework (IDs, stages, timeline, hashing), Text engine, URL engine, central risk engine, explanations, 2.0 frontend shell + landing + investigate + results + history + dashboard |
| 2 | pgvector RAG, source system, claim verification UI, PDF + OCR, LLM/search provider abstractions |
| 3 | Image forensics, image deepfake, audio, video (Celery, chunked), file ingestion security (magic-byte sniffing, cleanup) |
| 4 | Financial fraud (Isolation Forest), transaction features, transaction graph, QR |
| 5 | Knowledge graph, multimodal fusion, controlled multi-agent orchestration |
| 6 | Reports (PDF/CSV), analytics, model registry (MLflow), feedback |
| 7 | Security hardening, OpenTelemetry/Prometheus/Grafana, caching, per-role rate limits, cost tracking |
| 8 | E2E tests, CI/CD deploy stages, documentation set |
