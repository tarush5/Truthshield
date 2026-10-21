"""
Logging configuration shared by the API and the Celery worker.

`LOG_FORMAT=text` (the default) keeps the familiar one-line format.
`LOG_FORMAT=json` writes one JSON object per line for log shippers. Either
way every record carries the request id of the request it belongs to ("-"
outside a request), so a quoted id finds every line it produced.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

TEXT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            from truthshield.api.middleware import current_request_id

            record.request_id = current_request_id()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


def configure(level: str, fmt: str = "text", *, datefmt: str | None = None) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    if (fmt or "text").lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(TEXT_FORMAT, datefmt=datefmt))
    handler._truthshield = True
    root = logging.getLogger()
    # Replace, not add: configure() may run more than once in a process.
    for existing in [h for h in root.handlers if getattr(h, "_truthshield", False)]:
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)
