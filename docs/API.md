# API

Base path `/api/v1`. JSON in and out. Interactive OpenAPI docs are served at
`/docs` whenever `APP_ENV` is not `production`. In production the schema is
deliberately not published.

## Authentication

| Method | Header |
|---|---|
| User session | `Authorization: Bearer <access_token>` (JWT, HS256, 60 min) |
| Programmatic | `X-API-Key: ts_…` |

Access tokens are short-lived. Renew them with the refresh token:

| Endpoint | Body | Returns |
|---|---|---|
| `POST /auth/signup` | `{email, password}` | `201 TokenResponse` |
| `POST /auth/signin` | `{email, password}` | `200 TokenResponse` · `401` (same message for unknown account and wrong password) · `429` when locked out |
| `POST /auth/refresh` | `{refresh_token}` | `200 TokenResponse` (**rotates**: the old refresh token is revoked; replaying it revokes the whole chain) |
| `POST /auth/logout` | `{refresh_token}` | `204` |
| `POST /auth/otp`, `/auth/otp/verify` | email code sign-in | (1.x) |
| `GET /auth/me` | — | `{id, email, org_id, role}` |

`TokenResponse = {access_token, token_type: "bearer", expires_in, refresh_token, user: {id, email, org_id, role}}`

### Roles

| Role | Can |
|---|---|
| `USER` | Create, read, export and delete their own investigations |
| `ANALYST` | Same as `USER` in Phase 1. The role exists so analyst-only tooling (feedback review, threat-intel curation) can be gated without a migration |
| `ADMIN` | Everything, plus user and role management, the audit log, and reading any investigation (including its original input) |

The first admin is set with `BOOTSTRAP_ADMIN_EMAILS` (comma-separated). A
matching account is promoted when it signs up or signs in.

## Errors

Every error uses one envelope:

```json
{
  "error": { "code": "UNSUPPORTED_INPUT", "message": "…", "request_id": "9f1c…" },
  "detail": "…"
}
```

`detail` is kept for 1.x clients. The same `request_id` is sent in the
`X-Request-ID` header and in server logs. Stack traces are never returned.

| Status | `code` |
|---|---|
| 400 | `BAD_REQUEST`, `UNSUPPORTED_INPUT`, `BLOCKED_URL` |
| 401 | `UNAUTHENTICATED` |
| 403 | `FORBIDDEN` |
| 404 | `NOT_FOUND` (also returned for "exists but not yours") |
| 413 | `PAYLOAD_TOO_LARGE` |
| 422 | `VALIDATION_ERROR` (`detail` keeps FastAPI's field list) |
| 429 | `RATE_LIMITED`, `ACCOUNT_LOCKED` |
| 500 | `INTERNAL_ERROR` |
| 503 | `UNAVAILABLE` |

## Investigations (2.0)

### `POST /investigations` → `202`

```json
{ "type": "message", "content": "Congratulations! You have won ₹50,000 …", "language": "auto" }
```

`type`: `text` · `url` · `message` · `email`. Alternatively send
`{"demo_id": "phishing-sms"}` to run a synthetic sample through the **real**
pipeline (the result is flagged `is_demo`).

```json
{ "id": "3f0c…", "public_id": "TS-2026-000042", "status": "QUEUED",
  "links": { "self": "/api/v1/investigations/3f0c…" } }
```

### `GET /investigations`

Query: `q` (matches public id, redacted excerpt or input hash), `status`,
`risk_level`, `type`, `sort` (`-created_at` default, `created_at`,
`-risk_score`, `risk_score`), `page` (1-based), `page_size` (≤ 100).

```json
{ "items": [InvestigationSummary], "total": 128, "page": 1, "page_size": 20 }
```

### `GET /investigations/{id}`

`{id}` is either the UUID or the public id. The response contains the
summary fields, `timeline` (events), `risk_factors`, `model_predictions`,
`input` (original content visible to its owner; SHA-256; size) and
`result`, the structured payload:

```json
{
  "classification": "potential_phishing",
  "risk": { "score": 91, "level": "CRITICAL", "confidence": 0.82, "confidence_band": "HIGH",
            "represents": "Estimated likelihood that this content is part of a fraud or phishing attempt, from the signals listed. Not proof.",
            "contributions": [{ "code": "brand_outside_domain", "title": "Brand name used in a subdomain", "points": 21, "family": "url", "provenance": "heuristic" }],
            "families": { "url": { "score": 81, "weight": 20, "assessed": true } },
            "weights_version": "default-2026.10" },
  "signals": [ Signal ],
  "engines": [ { "name": "text", "version": "1.0.0", "status": "ok", "duration_ms": 12, "limitations": [] } ],
  "entities": { "urls": [], "emails": [], "phones": [], "amounts": [], "dates": [], "organizations": [] },
  "claims": [ { "id": "C1", "text": "…", "assessment": "INSUFFICIENT_EVIDENCE", "sources": [] } ],
  "url_intelligence": [ { "url": "…", "features": { "entropy": 3.9, "…": 0 }, "page": null } ],
  "language": { "detected": "en", "confidence": 0.99, "supported": true },
  "explanation": { "summary": "…", "llm": null },
  "uncertainties": [ "Domain registration age was not checked (no WHOIS provider configured)." ],
  "recommended_actions": [ "…" ]
}
```

### Other investigation routes

| Route | Notes |
|---|---|
| `GET /investigations/{id}/events` | The timeline only. Cheap to poll. |
| `GET /investigations/{id}/export?format=json\|csv` | Download. JSON is the full result with the redacted input. CSV is the risk factors. (PDF: Phase 6) |
| `DELETE /investigations/{id}` | `204`. Owner or admin. Cascades to inputs, events, factors and predictions. |

### Synchronous analysis

`POST /analyze/text`, `/analyze/url`, `/analyze/message`, `/analyze/email`,
with body `{content}` (for `/analyze/url`, `{url}`). These create an
investigation, run it inline, and return the full detail (`200`). They are
convenient for scripts. Media routes (`/analyze/image|audio|video|pdf`) land
in Phases 2–3.

## Platform

| Route | Auth | Notes |
|---|---|---|
| `GET /dashboard/summary?days=30` | user | Real aggregates over the caller's investigations (all of them for admins): totals, by level, by type, average risk, daily volume, p50/p95/p99 latency, recent items |
| `GET /engines` | user | Registered engines, versions, kinds, active risk weights |
| `GET /demo/samples` | public | Synthetic samples (no real personal data) |
| `GET /system/health` | public | DB, cache, broker, capabilities, evidence providers, engines |
| `GET /admin/users`, `PATCH /admin/users/{id}` | ADMIN | List users; change role or active flag (audited) |

## 1.x endpoints (kept)

`POST /analyze` (fact-check, multipart), `GET /analyze/stream` (SSE),
`GET /reports`, `GET /reports/{id}`, `POST /feedback`, `/fraud/*`,
`/insights/*`, `/claims/*`, `/reports/{id}/share`, `GET /shared/{token}`,
`GET /stats`, `GET /health`.
