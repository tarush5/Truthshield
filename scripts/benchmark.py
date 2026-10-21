"""
Offline latency benchmark, per input type, through the real app.

    python scripts/benchmark.py [--n 40] [--concurrency 8]

Runs the full HTTP + pipeline path in-process (inline executor, offline: no
page fetch, no live search, no LLM) against a throwaway SQLite database, so
the numbers measure TruthShield's own work. Network-bound stages (live
evidence search, page fetch, threat feeds over HTTP) are not represented and
would dominate a real online deployment.

Reports, per type: p50 / p95 / p99 end-to-end request latency and the
pipeline's own processing time, error rate, and throughput; then a
concurrent run; then peak Python heap (tracemalloc), which excludes native
allocations by OpenCV, NumPy and model weights.
"""

from __future__ import annotations

import os
import statistics
import sys
import tempfile
import time
import tracemalloc
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
_TMP = Path(tempfile.mkdtemp(prefix="ts-bench-"))
os.environ.update({
    "APP_ENV": "test",
    "JWT_SECRET_KEY": "benchmark-secret-key-that-is-long-enough-to-pass-validation",
    "DATABASE_URL": f"sqlite:///{(_TMP / 'bench.db').as_posix()}",
    "REDIS_URL": "redis://127.0.0.1:1",
    "INVESTIGATION_EXECUTOR": "inline",
    "OFFLINE_MODE": "true",
    "RATE_LIMIT": "1000000/minute", "RATE_LIMIT_AUTH": "1000000/minute", "RATE_LIMIT_ANALYSIS": "1000000/minute",
    "STORAGE_DIR": str(_TMP / "storage"),
    "INVESTIGATION_DEDUP_SECONDS": "0",
    "LOG_LEVEL": "WARNING",
})

MESSAGE = ("Dear customer, your SBI account KYC has expired and will be blocked today. "
           "Update immediately at http://sbi-kyc-update.top/verify {n}")
BENIGN = "Reached home safely, the train was late by an hour. Will call after dinner. {n}"
URL = "https://paypal-verify-{n}.github.io/login"


def _pct(values, q):
    values = sorted(values)
    return values[min(len(values) - 1, int(round(q * (len(values) - 1))))]


def _summary(name, walls, procs, errors, elapsed):
    n = len(walls) + errors
    print(f"{name:<22} n={n:<4} wall p50 {_pct(walls, .5):>5.0f}  p95 {_pct(walls, .95):>5.0f}  "
          f"p99 {_pct(walls, .99):>5.0f} ms | pipeline p50 {_pct(procs, .5):>5.0f}  p95 {_pct(procs, .95):>5.0f} ms | "
          f"errors {errors / n:.1%} | {len(walls) / elapsed:5.1f}/s")


def main(argv):
    n = int(argv[argv.index("--n") + 1]) if "--n" in argv else 40
    workers = int(argv[argv.index("--concurrency") + 1]) if "--concurrency" in argv else 8

    from alembic import command
    from alembic.config import Config
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(cfg, "head")

    from fastapi.testclient import TestClient
    from tests.pdf_factory import invoice
    from truthshield.main import app

    tracemalloc.start()
    with TestClient(app) as client:
        token = client.post("/api/v1/auth/signup", json={
            "email": f"bench{uuid.uuid4().hex[:8]}@example.com", "password": "correct-horse-42",
        }).json()["access_token"]
        auth = {"Authorization": f"Bearer {token}"}

        def text_job(kind, template):
            def job(i):
                return client.post("/api/v1/investigations", headers=auth,
                                   json={"type": kind, "content": template.format(n=f"{i}-{uuid.uuid4().hex[:6]}")})
            return job

        def pdf_job(i):
            data = invoice(number=f"B-{i}-{uuid.uuid4().hex[:6]}")
            return client.post("/api/v1/investigations/upload", headers=auth,
                               files={"file": (f"inv{i}.pdf", data, "application/pdf")})

        def measure(name, job, count, threads=1):
            walls, procs, errors = [], [], 0

            def one(i):
                t = time.perf_counter()
                r = job(i)
                wall = (time.perf_counter() - t) * 1000
                if r.status_code != 202:
                    return None
                inv = client.get(f"/api/v1/investigations/{r.json()['id']}", headers=auth).json()
                return (wall, inv.get("processing_ms") or 0) if inv.get("status") == "COMPLETED" else None

            job(-1)  # warm-up: first-use imports and caches are not steady state
            started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=threads) as pool:
                for outcome in pool.map(one, range(count)):
                    if outcome is None:
                        errors += 1
                    else:
                        walls.append(outcome[0])
                        procs.append(outcome[1])
            _summary(name, walls, procs, errors, time.perf_counter() - started)

        print(f"Offline, inline executor, SQLite. Python {sys.version.split()[0]}.")
        measure("message (scam)", text_job("message", MESSAGE), n)
        measure("message (benign)", text_job("message", BENIGN), n)
        measure("url", text_job("url", URL), n)
        measure("pdf invoice", pdf_job, max(5, n // 2))
        measure(f"message x{workers} threads", text_job("message", MESSAGE), n * 2, threads=workers)

    current, peak = tracemalloc.get_traced_memory()
    print(f"Peak Python heap during run: {peak / 1_048_576:.1f} MiB (tracemalloc; excludes native allocations)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
