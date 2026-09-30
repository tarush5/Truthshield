# Database

PostgreSQL 16 in every deployed environment. SQLite is allowed only when
`APP_ENV` is `development` or `test`, and the settings validator refuses it
in production. Alembic owns the schema: nothing is created by application
startup side effects.

Conventions:

- Primary keys are UUIDs (`GUID` type: native `uuid` on Postgres, `CHAR(36)` elsewhere). The one exception is the 1.x `reports` table, which keeps its `uuid4().hex` string id.
- Every table has `created_at` / `updated_at` (`timestamptz`, UTC).
- Flexible model output is stored as `JSONB` on Postgres and `JSON` elsewhere.
- Every foreign key declares `ondelete`. Columns that are filtered or sorted on are indexed.

## 1. Tables

### 1.1 Identity and access

| Table | Purpose | Key columns |
|---|---|---|
| `users` | Accounts | `email` (unique), `password_hash` (PBKDF2, nullable for OTP-only), `is_active`, **`role`** (`USER`/`ANALYST`/`ADMIN`, P1), **`last_login_at`** (P1) |
| `refresh_tokens` **(P1)** | Rotating refresh tokens | `user_id` → users CASCADE, `token_hash` (SHA-256, unique), `family_id` (rotation chain), `expires_at`, `revoked_at`, `replaced_by_id` |
| `organizations`, `organization_members` | Workspaces and per-workspace roles (1.x) | unique (`org_id`, `user_id`) |
| `api_keys` | Hashed programmatic keys (1.x) | `key_hash` unique, `key_prefix` |
| `audit_logs` | Who did what | `org_id`, `actor_id`, `action`, `detail` (JSON: resource, request_id, …) |

System roles (`users.role`) are platform-wide permissions. Workspace roles
(`organization_members.role`) scope data sharing. They answer different
questions and are kept separate.

A refresh token is stored only as its SHA-256. Presenting a token that has
already been rotated or revoked revokes its whole `family_id`: a stolen
token that is replayed after the legitimate client has rotated signs out
both parties.

### 1.2 Investigations (Phase 1)

```
investigations 1───* investigation_inputs      (immutable once written)
               1───* investigation_events      (append-only timeline)
               1───* risk_factors              (score contributions)
               1───* model_predictions         (versioned engine outputs)
investigation_counters                         (per-year public-id sequence)
```

**`investigations`**

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `public_id` | varchar(20) unique | `TS-2026-000001` |
| `user_id` | uuid → users SET NULL, indexed | owner |
| `org_id` | uuid → organizations CASCADE | workspace at creation |
| `type` | varchar(20), indexed | `text`, `url`, `message`, `email` (P1) |
| `status` | varchar(24), indexed | `QUEUED` … `COMPLETED` / `FAILED` |
| `risk_score` | int null | 0–100, set on completion |
| `risk_level` | varchar(12) null, indexed | `LOW` / `MEDIUM` / `HIGH` / `CRITICAL` |
| `confidence` | float null | 0–1 |
| `confidence_band` | varchar(12) null | |
| `language` | varchar(8) | detected |
| `input_sha256` | char(64), indexed | duplicate detection, provenance |
| `excerpt` | varchar(240) | **PII-redacted** preview for lists and search |
| `result` | JSONB | full structured result (see [AI services](AI_SERVICES.md)) |
| `error` | text null | operator-safe message |
| `is_demo` | bool | created from a synthetic demo sample |
| `processing_ms` | int null | end-to-end pipeline time |
| `started_at`, `completed_at` | timestamptz | |

Indexes: (`user_id`, `created_at`), `status`, `risk_level`, `type`, `input_sha256`.

**`investigation_inputs`**: `kind`, `content` (original, preserved unmodified),
`redacted_content`, `sha256`, `size_bytes`, `mime_type`, `filename`, `meta`
(JSON). Rows are never updated. Deleting the investigation deletes them
(CASCADE), which is how a user removes their data.

**`investigation_events`**: `seq`, `stage`, `status` (`started` / `completed` /
`skipped` / `failed`), `service`, `message`, `started_at`, `finished_at`,
`duration_ms`, `detail` (JSON). Only operational facts are recorded here,
never model reasoning.

**`risk_factors`**: `code`, `title`, `family`, `severity`, `provenance`,
`engine`, `engine_version`, `points` (the share of the final score),
`confidence`, `evidence` (verbatim excerpt), `explanation`.

**`model_predictions`**: `model_name`, `model_version`, `model_kind`
(`heuristic` / `ml` / `retrieval` / `llm`), `task`, `input_sha256`,
`prediction` (JSON), `confidence`, `created_at`. This makes an investigation
reproducible: the same input hash through the same engine version must give
the same prediction.

**`investigation_counters`**: `year` (PK), `value`. Allocation is a single
`UPDATE … SET value = value + 1 … RETURNING value`, which is atomic on both
Postgres and SQLite (≥ 3.35).

### 1.3 Legacy 1.x (unchanged)

`reports`, `evidence`, `feedback`: the fact-check report store. These are
still written by `/analyze` and read by history and share links.

## 2. Planned tables

| Table | Phase | Notes |
|---|---|---|
| `files` | 3 | Object-storage key, SHA-256, sniffed MIME, size, retention deadline |
| `claims` | 2 | Extracted claims normalised out of `result` for search |
| `sources` | 2 | Publisher, domain, category (`PRIMARY` / `OFFICIAL` / `SECONDARY` / `COMMUNITY` / `UNKNOWN`), first/last seen |
| `evidence_chunks` | 2 | `document_id`, `chunk_id`, text, `embedding vector(384)` (**pgvector**), metadata; HNSW index |
| `entities`, `relationships` | 5 | Knowledge graph as adjacency tables (`MENTIONS`, `SUPPORTS`, `CONTRADICTS`, …) |
| `transactions` | 4 | Normalised transaction rows plus engineered features |
| `reports` (v2) | 6 | Generated PDF/CSV artefacts per investigation |
| `model_registry` | 6 | Name, version, task, framework, dataset, **measured** metrics, status (mirrors MLflow) |
| `processing_jobs` | 3 | Celery job ids, queue, attempts, heartbeats |
| `investigation_feedback` | 6 | `feedback_type`, `model_version`, notes |

## 3. Retention and privacy

- `excerpt` and exported reports use the **redacted** text (Luhn-checked
  cards, OTPs, account numbers and phone numbers are masked; see
  `fraud/privacy.py`). The original is kept only in
  `investigation_inputs.content`, visible to its owner and admins.
- `DELETE /api/v1/investigations/{id}` removes the investigation and every
  dependent row.
- `INVESTIGATION_RETENTION_DAYS` (default 90) is enforced by a scheduled
  purge task in Phase 7.

## 4. Migrations

```bash
alembic upgrade head          # apply
alembic downgrade -1          # roll back one
alembic revision -m "..."     # new migration (hand-review autogenerate output)
```

CI applies every migration from empty, downgrades to base, and upgrades
again, so a migration that only works against an existing database fails
the build.
