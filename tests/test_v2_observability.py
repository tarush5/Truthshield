"""Metrics endpoint and structured logging."""

import json
import logging
import uuid

from truthshield.infra import metrics
from truthshield.infra.logging_setup import JsonFormatter, RequestIdFilter


def account(client, role=None):
    email = f"m{uuid.uuid4().hex[:10]}@example.com"
    body = client.post("/api/v1/auth/signup", json={"email": email, "password": "correct-horse-42"}).json()
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    if role:
        from truthshield.infra.database import SessionLocal
        from truthshield.infra.models import User
        s = SessionLocal()
        s.get(User, uuid.UUID(body["user"]["id"])).role = role
        s.commit()
        s.close()
    return headers


class TestMetrics:
    def test_admin_only(self, client):
        assert client.get("/api/v1/system/metrics").status_code == 401
        assert client.get("/api/v1/system/metrics", headers=account(client)).status_code == 403

    def test_routes_are_templated_and_counts_exposed(self, client):
        admin = account(client, role="ADMIN")
        metrics.reset()
        missing = uuid.uuid4()
        for _ in range(2):
            client.get(f"/api/v1/investigations/{missing}", headers=admin)
        r = client.get("/api/v1/system/metrics", headers=admin)
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
        body = r.text
        assert str(missing) not in body, "raw ids must never become labels"
        assert ('truthshield_http_requests_total{method="GET",route="/api/v1/investigations/{ident}",'
                'status="4xx"} 2') in body
        assert 'truthshield_http_request_duration_seconds_count{route="/api/v1/investigations/{ident}"} 2' in body
        assert "truthshield_reviews_open " in body
        assert "truthshield_process_uptime_seconds" in body

    def test_histogram_buckets_are_cumulative(self):
        metrics.reset()
        metrics.observe("GET", "/x", 200, 0.07)
        metrics.observe("GET", "/x", 200, 3.0)
        text = metrics.render()
        assert 'le="0.05"} 0' in text and 'le="0.1"} 1' in text and 'le="5.0"} 2' in text
        assert 'le="+Inf"} 2' in text


class TestLogging:
    def _record(self, msg="hello %s", args=("world",), exc_info=None):
        return logging.LogRecord("truthshield.test", logging.INFO, __file__, 1, msg, args, exc_info)

    def test_json_lines_carry_the_request_id(self):
        from truthshield.api.middleware import request_id_var

        token = request_id_var.set("abc123")
        try:
            record = self._record()
            RequestIdFilter().filter(record)
        finally:
            request_id_var.reset(token)
        data = json.loads(JsonFormatter().format(record))
        assert data["message"] == "hello world" and data["request_id"] == "abc123"
        assert data["level"] == "INFO" and data["logger"] == "truthshield.test"

    def test_outside_a_request_the_id_is_a_dash(self):
        record = self._record()
        RequestIdFilter().filter(record)
        assert record.request_id == "-"

    def test_exceptions_are_included(self):
        try:
            raise ValueError("bad")
        except ValueError:
            import sys
            record = self._record(exc_info=sys.exc_info())
        assert "ValueError: bad" in json.loads(JsonFormatter().format(record))["exception"]
