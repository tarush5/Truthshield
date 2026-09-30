# Workers and asynchronous processing

## Executors

`INVESTIGATION_EXECUTOR` decides where an investigation's pipeline runs:

| Value | Where | Use |
|---|---|---|
| `inline` | Inside the request | Tests; `/analyze/*` synchronous routes (always inline) |
| `background` (default) | FastAPI's thread pool, after the `202` is sent | Text and URL. I/O-bound, finishes in seconds, needs no broker |
| `celery` | `truthshield.investigations.tasks.run_investigation` on the Celery worker | Production fleets; required for heavy media |

Heavy modalities (image, audio, video, large PDF) **always** go to Celery
from Phase 3, whatever this setting says. The API process never decodes
media.

If the broker is unreachable when `celery` is selected, the API returns
`503 UNAVAILABLE`. It does not quietly run the job in-process. This is the
1.x rule: an in-process fallback blocked request threads and lost jobs on
restart while reporting them as queued.

## Queues (Phase 3+)

| Queue | Tasks | Concurrency |
|---|---|---|
| `default` | text, URL, evidence retrieval, report generation | threads, 4 |
| `media` | OCR, image forensics, deepfake, audio, video | prefork, 1–2 per CPU, memory-limited |
| `embeddings` | chunk + embed + index (pgvector) | batched |

Worker rules:

- Stream files from object storage to a per-task temp dir. Delete it in `finally`.
- Video: sample frames at a configurable rate in chunks. Never hold the whole file.
- Resize images before inference. Batch model calls. Use GPU when present, CPU otherwise.
- `task_acks_late`, `worker_max_tasks_per_child` (to cap memory growth), hard and soft time limits.
- Each stage writes an `investigation_events` row, so progress is visible without polling the worker.

## Status delivery

Phase 1 clients poll `GET /investigations/{id}` (React Query, 800 ms while
in flight). The events are persisted, so an SSE stream (1.x already streams
the fact-check pipeline) can be layered on without changing the pipeline.

## Retention jobs (Phase 7)

Celery beat runs `purge_expired_investigations` daily, honouring
`INVESTIGATION_RETENTION_DAYS`.
