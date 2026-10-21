"""
Request and pipeline metrics in the Prometheus text format.

Hand-written rather than a new dependency: a few counters and one histogram.
Two things a reader of the numbers should know:

* Request metrics are per process. Behind several workers, scrape each one
  (or sum them); a single scrape sees only the worker that answered it.
* Routes are labelled by their template ("/investigations/{ident}"), never by
  the raw path, so ids cannot blow up the label set.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Dict, Iterable, Tuple

BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)
_STARTED = time.time()

_lock = threading.Lock()
_requests: Dict[Tuple[str, str, str], int] = defaultdict(int)
_durations: Dict[str, list] = {}   # route -> [bucket counts..., +Inf count, sum]


def observe(method: str, route: str, status: int, seconds: float) -> None:
    status_class = f"{status // 100}xx"
    with _lock:
        _requests[(method, route, status_class)] += 1
        row = _durations.setdefault(route, [0] * (len(BUCKETS) + 2))
        for i, bound in enumerate(BUCKETS):
            if seconds <= bound:
                row[i] += 1
        row[len(BUCKETS)] += 1
        row[len(BUCKETS) + 1] += seconds


def reset() -> None:
    with _lock:
        _requests.clear()
        _durations.clear()


def _label(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def render(gauges: Iterable[Tuple[str, str, Dict[str, str], float]] = ()) -> str:
    """Exposition text. `gauges` are (name, help, labels, value) computed by the caller."""
    lines = [
        "# HELP truthshield_http_requests_total HTTP requests handled by this process.",
        "# TYPE truthshield_http_requests_total counter",
    ]
    with _lock:
        requests = sorted(_requests.items())
        durations = {k: list(v) for k, v in sorted(_durations.items())}
    for (method, route, status), n in requests:
        lines.append(f'truthshield_http_requests_total{{method="{method}",route="{_label(route)}",'
                     f'status="{status}"}} {n}')
    lines += [
        "# HELP truthshield_http_request_duration_seconds Request latency by route, this process.",
        "# TYPE truthshield_http_request_duration_seconds histogram",
    ]
    for route, row in durations.items():
        r = _label(route)
        for i, bound in enumerate(BUCKETS):
            lines.append(f'truthshield_http_request_duration_seconds_bucket{{route="{r}",le="{bound}"}} {row[i]}')
        lines.append(f'truthshield_http_request_duration_seconds_bucket{{route="{r}",le="+Inf"}} {row[len(BUCKETS)]}')
        lines.append(f'truthshield_http_request_duration_seconds_sum{{route="{r}"}} {row[len(BUCKETS) + 1]:.6f}')
        lines.append(f'truthshield_http_request_duration_seconds_count{{route="{r}"}} {row[len(BUCKETS)]}')

    seen = set()
    for name, help_text, labels, value in gauges:
        if name not in seen:
            lines += [f"# HELP {name} {help_text}", f"# TYPE {name} gauge"]
            seen.add(name)
        label_text = ",".join(f'{k}="{_label(v)}"' for k, v in labels.items())
        lines.append(f"{name}{{{label_text}}} {value}" if label_text else f"{name} {value}")

    lines += [
        "# HELP truthshield_process_uptime_seconds Seconds since this process started.",
        "# TYPE truthshield_process_uptime_seconds gauge",
        f"truthshield_process_uptime_seconds {time.time() - _STARTED:.0f}",
    ]
    return "\n".join(lines) + "\n"
