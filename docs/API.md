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
| `POST /investigations/{id}/reanalyze` | `202`. Owner or admin. Re-runs the current pipeline over the stored input as a **new** investigation; the original is untouched. The new one's detail has `reanalysis_of` with the previous score, level, config version and `changes` (signals added/removed, claims changed, engine/config versions changed, plain `reasons`). |
| `POST /investigations/{id}/feedback` | `201`. Owner or admin. `{label: fraud\|legitimate\|unsure, category?, finding?, comment?, appeal?}`. `category`: `false_positive`, `missed_threat`, `incorrect_evidence`, `broken_citation`, `outdated_information`, `unclear_explanation`, `other`. `finding` must be a signal code or claim id from this result. Comments are redacted before storage. `appeal: true` asks for human review (one open appeal at a time, `409 APPEAL_OPEN`). Never changes the result. |
| `GET /investigations/{id}/reviews` | Feedback, appeals and reviewer decisions on this investigation. |

### Synchronous analysis

`POST /analyze/text`, `/analyze/url`, `/analyze/message`, `/analyze/email`,
with body `{content}` (for `/analyze/url`, `{url}`). These create an
investigation, run it inline, and return the full detail (`200`). They are
convenient for scripts. Media routes (`/analyze/image|audio|video|pdf`) land
in Phases 2–3.

### Result fields added in October 2026

| Field | Meaning |
|---|---|
| `risk.determination`, `risk.abstention_reason` | `ASSESSED`, or `INCONCLUSIVE` when no signal fired but an applicable check did not run or could not read the input (e.g. an unsupported language). Score and level are unchanged; `classification` is `inconclusive`. |
| `recommended_actions.urgency`, `.urgency_note` | `act_now`, `verify_first`, `stay_alert`, or `unverified` (abstained), from the level. |
| `email_authentication` | For email input: SPF/DKIM/DMARC read from the topmost `Authentication-Results` header of pasted full headers (`checked`, `spf`, `dkim[]`, `dmarc`, `authserv_id`, `dkim_aligned`), or `{checked: false}`. Read, never re-verified; a pass never lowers risk. |
| `url_intelligence[].reputation` | `{checked, listed, match, status}` with `status` `KNOWN_MALICIOUS` / `NO_KNOWN_LISTING` / `NOT_CHECKED` (local threat feeds, `THREAT_FEED_PATHS`). |
| `url_intelligence[].structure` | `SUSPICIOUS` or `NO_STRUCTURAL_INDICATORS` -- "looks like", never "known". |
| `claims[].corroboration` | `{level: official\|multiple_independent\|single_source, independent_publishers, publishers, credible_publishers}`; copies on one publisher count once. Descriptive only. |
| `claims[].sources[].citation` | `{status: verified\|unverified\|mismatch, url_valid, publisher_matches_url, passage_found_in_source, passage_truncated, published_date, age_days, problems[]}`. A `mismatch` citation never decides a claim. `claims[].citations` counts each status. |
| `claims[].sources[].attribution` | `evidence_store` (a stored chunk) or `search_snippet`. |
| `image.qr` | Decoded QR codes: `url` (added to the investigation's URLs), `upi_payment` (payee, amount; an INFO signal explains that scanning only ever pays), or `text`. |
| `reanalysis_of`, `review` (detail) | Link to the run this one re-ran, with `changes`; review state (`count`, `open_appeal`, `reviewer_label`, `reviewed_at`). |

## Files (Phase 2)

| Route | Notes |
|---|---|
| `POST /investigations/upload` | multipart `file`: PDF, PNG, JPEG, WebP up to `MAX_UPLOAD_SIZE_MB`. `415 UNSUPPORTED_FILE` when the extension is not allowed **or the bytes do not match it**; `413` over the cap. Returns `202` like `POST /investigations` |
| `POST /analyze/pdf`, `POST /analyze/image` | Same, run inline, full result returned |
| `GET /investigations/{id}/file` | The upload, to its owner or an admin, with `X-Content-Type-Options: nosniff`, `Content-Security-Policy: sandbox`, `Cache-Control: private, no-store` |

Result additions: `result.document` (type, fields, metadata, active content, incremental saves, OCR),
`result.image` (dimensions, EXIF, OCR text and word boxes), `claims[].retrieval` (query variants, live-search
outcome, embedding kind, reranker) and `claims[].sources[].scores`, and `explanation.llm` / `llm_status` / `llm_meta`.

## Evidence (Phase 2)

| Route | Auth | Notes |
|---|---|---|
| `GET /evidence/search?q=&category=&min_credibility=&exclude_domain=&limit=` | user | Hybrid search; each result carries `scores.components` |
| `GET /evidence/stats` | user | Counts, backend (`pgvector` or in-process), embedding model and kind, reranker |
| `GET /evidence/{document_id}` | user | Document with chunks (no vectors) |
| `POST /evidence/documents` | ANALYST, ADMIN | `{url}` (fetched through the SSRF guard) or `{title, text, source_url}`; audited |
| `GET /sources?q=&category=` | user | Source registry |
| `PATCH /sources/{id}` | ADMIN | `{category, credibility, notes}`; marks the source curated; audited |
| `GET /claims?q=&assessment=` | user | Claims from your investigations (all, for admins) |

## Platform

| Route | Auth | Notes |
|---|---|---|
| `GET /dashboard/summary?days=30` | user | Real aggregates over the caller's investigations (all of them for admins): totals, by level, by type, average risk, daily volume, p50/p95/p99 latency, recent items |
| `GET /dashboard/patterns?days=30&limit=15` | user | Risk factors and classifications in this window vs the previous one (counts and change), scoped like the summary. Submission counts, not prevalence. |
| `GET /system/metrics` | ADMIN | Prometheus text: request counts and latency histogram per route template (per process), investigations by status and level, open appeals, uptime |
| `GET /admin/reviews?status=open\|recorded\|resolved\|all&kind=` | ANALYST, ADMIN | Review queue, oldest first |
| `GET /admin/reviews/{id}` | ANALYST, ADMIN | One review. Redacted input and result are included **only for appeals**; plain feedback shows label, category and comment |
| `PATCH /admin/reviews/{id}` | ANALYST, ADMIN | `{label: fraud\|legitimate\|inconclusive, note?}`. Stored beside the automated result, never written into it; a reviewer cannot decide their own appeal; audited |
| `GET /admin/reviews/accuracy?days=90` | ANALYST, ADMIN | Automated result vs reviewer decisions: confusion matrix, precision, recall, FPR, agreement by confidence band, with counts and the selection-bias caveat |
| `GET /engines` | user | Registered engines, versions, kinds, active risk weights |
| `GET /demo/samples` | public | Synthetic samples (no real personal data) |
| `GET /system/health` | public | DB, cache, broker, capabilities, evidence providers, engines |
| `GET /admin/users`, `PATCH /admin/users/{id}` | ADMIN | List users; change role or active flag (audited) |

## 1.x endpoints (kept)

`POST /analyze` (fact-check, multipart), `GET /analyze/stream` (SSE),
`GET /reports`, `GET /reports/{id}`, `POST /feedback`, `/fraud/*`,
`/insights/*`, `/claims/*`, `/reports/{id}/share`, `GET /shared/{token}`,
`GET /stats`, `GET /health`.
