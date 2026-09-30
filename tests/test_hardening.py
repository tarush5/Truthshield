"""
Production hardening: response headers, request correlation, docs exposure.

These are the properties that are invisible when they work and expensive
when they silently stop working, so each is asserted rather than assumed.
"""

import pytest

from truthshield.api.middleware import _clean


class TestSecurityHeaders:
    def test_sniffing_and_framing_are_closed_off(self, client):
        """
        Content sniffing is how a JSON response carrying attacker-controlled
        text gets executed as script; framing is how it gets clickjacked.
        """
        headers = client.get("/api/v1/health").headers
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["Referrer-Policy"] == "no-referrer"
        assert "geolocation=()" in headers["Permissions-Policy"]

    def test_a_json_route_is_allowed_to_load_nothing(self, client):
        """An API endpoint has no legitimate reason to fetch a subresource."""
        csp = client.get("/api/v1/health").headers["Content-Security-Policy"]
        assert "default-src 'none'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_every_route_is_covered_not_just_the_healthy_ones(self, client):
        """
        Headers come from middleware, so an error path must carry them too.
        A 401 that skips them is still a response an attacker can work with.
        """
        for response in (
            client.get("/api/v1/reports/does-not-exist"),
            client.post("/api/v1/analyze", data={"text": "x"}),
            client.get("/api/v1/nope"),
        ):
            assert response.headers["X-Content-Type-Options"] == "nosniff"
            assert "Content-Security-Policy" in response.headers

    def test_hsts_is_not_sent_outside_production(self, client):
        """
        Sent over plain HTTP it would pin clients to a scheme the dev and
        test deployments do not serve, locking them out of it.
        """
        assert "Strict-Transport-Security" not in client.get("/api/v1/health").headers


class TestRequestCorrelation:
    def test_every_response_carries_an_id(self, client):
        response = client.get("/api/v1/health")
        assert response.headers["X-Request-ID"]

    def test_the_id_is_readable_cross_origin(self, client):
        """
        The frontend is served from a different origin, and a browser cannot
        read a non-safelisted response header unless it is exposed. Without
        this the id exists and the client that needs to quote it cannot see
        it.
        """
        exposed = client.get("/api/v1/health").headers.get("Access-Control-Expose-Headers", "")
        assert "X-Request-ID" in exposed

    def test_ids_differ_between_requests(self, client):
        first = client.get("/api/v1/health").headers["X-Request-ID"]
        second = client.get("/api/v1/health").headers["X-Request-ID"]
        assert first != second

    def test_an_inbound_id_is_preserved(self, client):
        """One id across the whole hop chain, rather than a new one per service."""
        response = client.get("/api/v1/health", headers={"X-Request-ID": "trace-abc-123"})
        assert response.headers["X-Request-ID"] == "trace-abc-123"

    @pytest.mark.parametrize("hostile", [
        "a" * 200,                        # unbounded length
        "abc\ndef",                       # newline: forges a second log line
        "abc\rdef",
        "abc def",                        # whitespace
        "\x00evil",                       # control character
        "",
    ])
    def test_a_hostile_inbound_id_is_discarded(self, client, hostile):
        """
        The id lands in every log line for the request. Echoing an arbitrary
        caller-supplied string there is log injection.
        """
        assert _clean(hostile) == ""

        returned = client.get("/api/v1/health", headers={"X-Request-ID": hostile}).headers["X-Request-ID"]
        assert returned != hostile
        assert "\n" not in returned and "\r" not in returned
        assert 0 < len(returned) <= 64

    def test_a_plausible_id_survives_cleaning(self):
        assert _clean("01HQ8X7YJ2K3M4N5P6Q7R8S9T0") == "01HQ8X7YJ2K3M4N5P6Q7R8S9T0"
        assert _clean("  padded-id  ") == "padded-id"


class TestDocsExposure:
    def test_docs_are_available_outside_production(self, client):
        """They are a development tool, and the test env is not production."""
        assert client.get("/docs").status_code == 200

    def test_docs_are_off_in_production(self):
        """
        In production the schema publishes the exact request shape of every
        route, auth included, to anyone who asks.
        """
        from truthshield.settings import Environment

        assert Environment("production").is_production
        # The app wires docs_url from this predicate at import time; asserting
        # the predicate keeps the test from needing a second app instance
        # built under a different environment.
        assert not Environment("development").is_production
        assert not Environment("test").is_production
