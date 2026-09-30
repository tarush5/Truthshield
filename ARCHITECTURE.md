# TruthShield 2.0 — Architecture

> Multimodal fraud, misinformation, deepfake and digital-trust investigation platform.

This document describes the system **as built**, with planned components
marked by phase. The previous version of this file described components that
were never implemented. Every claim below points at code, or is labelled
*planned*.

Companion documents: [Migration](docs/MIGRATION.md) · [Database](docs/DATABASE.md) ·
[API](docs/API.md) · [AI services](docs/AI_SERVICES.md) · [Workers](docs/WORKERS.md) ·
[Frontend](docs/FRONTEND.md) · [Roadmap](docs/ROADMAP.md)

---

## 1. System context

```
                ┌──────────────────────────────────────────────┐
                │  React 19 + TypeScript SPA  (frontend/)      │
                │  React Query · Zustand · Tailwind · Motion   │
                └───────────────────────┬──────────────────────┘
                                        │ HTTPS, JSON, Bearer JWT
                ┌───────────────────────▼──────────────────────┐
                │  FastAPI gateway  (truthshield/main.py)      │
                │  request-id · security headers · CORS ·      │
                │  rate limits · error envelope · RBAC deps    │
                └───┬───────────────┬───────────────┬──────────┘
                    │               │               │
        ┌───────────▼───┐   ┌───────▼────────┐   ┌──▼──────────────┐
        │ Auth service  │   │ Investigation  │   │ Legacy 1.x       │
        │ JWT + refresh │   │ service        │   │ /analyze, /fraud │
        │ roles, audit  │   │ (2.0 core)     │   │ /reports, /shared│
        └───────────────┘   └───────┬────────┘   └──────────────────┘
                                    │ runs pipeline (inline, background thread, or Celery)
                    ┌───────────────▼────────────────────────────┐
                    │           Investigation pipeline           │
                    │  VALIDATION → HASHING → EXTRACTION →       │
                    │  CLASSIFICATION → FEATURES → MODEL ANALYSIS│
                    │  → EVIDENCE → CROSS-MODAL → RISK →         │
                    │  EXPLANATION → REPORT → STORAGE            │
                    └──┬──────────┬───────────┬──────────┬──────┘
                       │          │           │          │
                 ┌─────▼───┐ ┌────▼────┐ ┌────▼─────┐ ┌──▼──────────────┐
                 │ Text    │ │ URL     │ │ Evidence │ │ Media/Document/ │
                 │ engine  │ │ engine  │ │ engine   │ │ Fraud engines   │
                 │ (P1)    │ │ (P1)    │ │ (P1→P2)  │ │ (P2–P4, planned)│
                 └─────┬───┘ └────┬────┘ └────┬─────┘ └─────────────────┘
                       └──────────┴─────┬─────┘
                                  ┌─────▼──────┐     ┌───────────────────┐
                                  │ Risk engine │────►│ Explanation layer │
                                  └─────┬──────┘     └─────────┬─────────┘
                                        └──────────┬───────────┘
                          ┌────────────────────────▼─────────────────────┐
                          │ PostgreSQL (SQLite outside production)       │
                          │ investigations · inputs · events · risk      │
                          │ factors · model predictions · audit logs     │
                          └──────────────────────────────────────────────┘
          Redis: cache (URL analysis, OTP, login-failure counters), Celery broker
```

## 2. Core concepts

### 2.1 Investigation

The 2.0 unit of work. Created by `POST /api/v1/investigations`, given a
human-quotable ID (`TS-2026-000001`), and moved through a fixed status
machine:

```
QUEUED → PROCESSING → ANALYZING → COLLECTING_EVIDENCE → CALCULATING_RISK → COMPLETED
                                                                          ↘ FAILED
```

Every stage transition is written to `investigation_events` with a timestamp,
the service that ran it, its outcome (`completed`, `skipped` or `failed`) and
its duration. That table is the audit trail: append-only, never rewritten.

### 2.2 Engines

An **engine** is a pluggable analyser (`truthshield/investigations/engines/base.py`):

```python
class Engine:
    name: str; version: str; kind: "heuristic" | "ml" | "retrieval" | "llm"
    def applies_to(ctx) -> bool
    def run(ctx) -> EngineResult   # never raises; failures become status="error"
```

`EngineResult` carries a `status` (`ok`, `unavailable`, `error` or
`not_applicable`), **signals**, **features**, **artifacts** (entities,
claims, page metadata), **limitations**, and **model predictions** (name,
version, input hash, output, confidence).

An engine that did not run can never contribute a clean result. This carries
over 1.x's `DetectorStatus` rule.

### 2.3 Signals and provenance

Every risk-relevant observation is a `Signal`:

| Field | Meaning |
|---|---|
| `code`, `title`, `explanation` | What was detected and why it matters |
| `family` | `nlp`, `url`, `reputation`, `behavioral`, `document_media`, or `evidence`. Selects the risk weight |
| `severity` | `info`, `low`, `medium` or `high` |
| `provenance` | `heuristic`, `ml_prediction`, `retrieved` or `llm`. **How we know** |
| `evidence` | The verbatim excerpt from the input (or source) that triggered it |
| `engine`, `engine_version`, `confidence` | Who produced it, reproducibly |

The result payload keeps six kinds of information apart, as §0 of the spec
requires:

| Kind | Where it appears |
|---|---|
| **Verified evidence** | `input` (SHA-256, extracted URLs/entities), verbatim `signal.evidence` |
| **Retrieved information** | `evidence.claims[].sources[]` (publisher, URL, retrieved_at, stance) |
| **Heuristic signals** | `signals[]` with `provenance="heuristic"` |
| **ML predictions** | `signals[]` / `model_predictions[]` with `provenance="ml_prediction"` |
| **LLM interpretation** | `explanation.llm` (null unless a provider is configured) |
| **Uncertainty** | `uncertainties[]`, plus per-engine `limitations` |

### 2.4 Central risk engine

`truthshield/investigations/risk.py`. The weights are configuration, not
code: the defaults are in `risk_config.py` and can be overridden with
`RISK_WEIGHTS_JSON`.

1. **Family score** `s_f ∈ [0,100]` comes from the family's signals using 1.x's
   `score_from_indicators`. Contributions decay by position (1.0, 0.72, 0.52, …),
   and a lone signal is capped at 45, so one keyword cannot reach CRITICAL.
2. **Reliability** `r_f = w_f / max(w)`, from the configured family weights
   (NLP 20, URL 20, reputation 15, behavioral 15, document/media 15, evidence 15).
3. **Combination: noisy-OR.** `risk = 100 · (1 − Π_f (1 − r_f · s_f/100))`.
   A family that found nothing contributes a factor of 1, so clean families
   **do not dilute** a strong signal. A weighted average would let three
   empty checks hide one confident phishing finding. Independent families
   that agree push the score up.
4. **Attribution.** Each family receives `risk · a_f / Σa` points, where
   `a_f = −ln(1 − r_f·s_f/100)`. This is the exact log-share of the product,
   so the points sum to the score. Points are split across a family's
   signals by their decayed contributions and rounded by largest remainder.
   The UI shows every contribution, e.g. `+21 Domain mismatch`.
5. **Level.** `LOW < 40 ≤ MEDIUM < 65 ≤ HIGH < 85 ≤ CRITICAL`.
6. **Confidence** is a separate axis. It is computed from engine coverage,
   the confidence of the leading signals and cross-family agreement. It is
   capped at 0.85 when nothing beyond heuristics corroborates the result,
   and at 0.35 when no signal fired, because absence of evidence is weak
   evidence.

Every assessment returns the weights snapshot it used and a one-line
statement of what the score represents.

## 3. Request lifecycle

```
POST /api/v1/investigations {type, content}
  ├─ validate (size, type, SSRF check for URLs)            ← 400/413 on failure
  ├─ allocate TS-YYYY-NNNNNN (counter row, atomic UPDATE…RETURNING)
  ├─ write investigation (QUEUED) + immutable input row (SHA-256)
  ├─ audit_logs: investigation.create
  └─ 202 {id, public_id, status}
        │
        ▼ executor (INVESTIGATION_EXECUTOR = inline | background | celery)
  InvestigationRunner.run(id)
    for stage in STAGES: record event(started) → work → event(completed|skipped|failed)
    persist: result payload, risk_factors, model_predictions, status COMPLETED
GET /api/v1/investigations/{id}   ← the client polls this for status and timeline
```

`background` (the default) runs the pipeline in the API's worker thread pool
after the response is sent. That suits text and URL work, which is
I/O-bound and finishes in seconds. `celery` sends it to the worker fleet.
Heavy media (Phase 3) always goes through Celery, whatever this setting says.

## 4. Security boundaries

- **Untrusted input stays data.** Submitted text, fetched pages and retrieved
  documents are never interpolated into an instruction channel. Phase 1 has
  no LLM in the decision path. The text engine flags instruction-like
  content aimed at AI systems (`prompt_injection_attempt`) so an analyst can
  see it.
- **SSRF.** Every server-side fetch goes through `security.url_guard.safe_get`:
  scheme allowlist, resolved-address checks, per-hop redirect validation and
  a byte cap. The URL engine fetches only when `URL_FETCH_ENABLED=true`,
  never executes scripts, and records the redirect chain.
- **AuthN/Z.** Access JWT (60 min) plus a rotating refresh token (hashed at
  rest, family-revoked on reuse). System roles are `USER`, `ANALYST` and
  `ADMIN`, enforced by `require_role`. Objects are scoped to their owner,
  and admins can read everything.
- **Abuse.** Global rate limit, a stricter limit on auth routes, and a
  per-email failed-login lockout keyed by email hash, so a lockout reveals
  nothing about whether the account exists.
- **Errors.** A uniform envelope `{"error": {code, message, request_id}}` (plus
  a 1.x-compatible `detail`). Stack traces are only ever logged.

## 5. Deployment topology

`docker compose up` starts postgres, redis, migrate, api, worker and web.
Render (`render.yaml`) and Vercel host the same images. Observability
(Prometheus, Grafana, OpenTelemetry) and object storage (MinIO/S3) join the
compose file in Phase 7 and Phase 3 respectively. See [ROADMAP](docs/ROADMAP.md).
