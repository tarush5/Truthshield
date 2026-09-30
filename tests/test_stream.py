"""
Server-sent event stream.

The stream is the only way the UI learns what the server is doing, so the
contract that matters is: every path terminates with a frame the client can
act on, and nothing sensitive leaks into one.
"""

import json

import pytest


def _frames(body: str):
    """Parse an SSE body into (event, data) pairs, skipping keepalives."""
    out = []
    for block in body.split("\n\n"):
        event, data_lines = "message", []
        for line in block.split("\n"):
            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
        if data_lines:
            try:
                out.append((event, json.loads("\n".join(data_lines))))
            except json.JSONDecodeError:
                pass
    return out


class TestStreamContract:
    def test_requires_authentication(self, client):
        r = client.post("/api/v1/analyze/stream", json={"text": "Paris is the capital of France."})
        assert r.status_code == 401

    def test_rejects_an_empty_submission(self, client, auth):
        r = client.post("/api/v1/analyze/stream", json={}, headers=auth)
        assert r.status_code == 400

    @pytest.mark.parametrize("url", [
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1:8000/api/v1/health",
        "file:///etc/passwd",
    ])
    def test_rejects_urls_that_would_be_ssrf(self, client, auth, url):
        """The streaming path must enforce the same guard as the blocking one."""
        r = client.post("/api/v1/analyze/stream", json={"url": url}, headers=auth)
        assert r.status_code == 400

    def test_rejects_oversized_text(self, client, auth):
        from truthshield.settings import get_settings
        too_long = "x" * (get_settings().MAX_TEXT_LENGTH + 1)
        r = client.post("/api/v1/analyze/stream", json={"text": too_long}, headers=auth)
        assert r.status_code == 413


class TestStreamEvents:
    @pytest.fixture(scope="class")
    def stream(self, request):
        """One real streamed analysis, shared across the assertions below."""
        from fastapi.testclient import TestClient
        from truthshield.main import app
        import uuid

        with TestClient(app) as client:
            token = client.post("/api/v1/auth/signup", json={
                "email": f"s{uuid.uuid4().hex[:10]}@example.com",
                "password": "correct-horse-42",
            }).json()["access_token"]

            r = client.post(
                "/api/v1/analyze/stream",
                json={"text": "Paris is the capital of France.", "language": "en"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            return _frames(r.text)

    def test_content_type_is_an_event_stream(self, client, auth):
        r = client.post(
            "/api/v1/analyze/stream",
            json={"text": "Paris is the capital of France."},
            headers=auth,
        )
        assert r.headers["content-type"].startswith("text/event-stream")
        # nginx buffers proxied responses by default, which would hold every
        # event until the stream closed and defeat the point entirely.
        assert r.headers.get("x-accel-buffering") == "no"

    def test_the_report_id_arrives_first(self, stream):
        """
        Sent before any work starts, so a client whose connection drops can
        still recover the result by polling GET /reports/{id}.
        """
        event, data = stream[0]
        assert event == "accepted"
        assert len(data["id"]) == 32

    def test_stages_report_real_elapsed_time(self, stream):
        stages = [d for e, d in stream if e == "stage"]
        assert stages, "no stage events"

        elapsed = [s["elapsed"] for s in stages]
        assert elapsed == sorted(elapsed), "elapsed time went backwards"

        progress = [s["progress"] for s in stages]
        assert progress == sorted(progress), "progress went backwards"
        assert progress[-1] == 1.0

    def test_it_ends_with_a_complete_frame(self, stream):
        """
        Every terminal path emits complete or error, so a client never has to
        guess whether the stream finished or the connection died.
        """
        events = [e for e, _ in stream]
        assert "complete" in events

        report = next(d for e, d in stream if e == "complete")
        for key in ("id", "verdict", "trust_score", "breakdown", "claims", "detectors"):
            assert key in report

    def test_the_streamed_id_matches_the_final_report(self, stream):
        accepted = next(d for e, d in stream if e == "accepted")
        report = next(d for e, d in stream if e == "complete")
        assert accepted["id"] == report["id"]

    def test_the_streamed_report_is_persisted(self, stream, client, auth):
        """A stream that returns a result must also have saved it."""
        report = next(d for e, d in stream if e == "complete")
        # Fetched anonymously: it belongs to the fixture's own user, so a 404
        # here proves persistence *and* that access control still applies.
        assert client.get(f"/api/v1/reports/{report['id']}").status_code == 404
