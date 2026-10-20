"""
Request-level hardening found in the October 2026 audit.

- Oversized bodies are refused before they are read (BodySizeLimitMiddleware).
- CORS allows PATCH, which the admin endpoints use.
"""

import asyncio

from truthshield.api.middleware import BodySizeLimitMiddleware


def _run(app, *, headers, chunks):
    """Drive an ASGI app with a body sent in `chunks`; return (status, app_saw_bytes)."""
    sent = []
    queue = [{"type": "http.request", "body": c, "more_body": i < len(chunks) - 1} for i, c in enumerate(chunks)]

    async def receive():
        return queue.pop(0) if queue else {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "method": "POST", "path": "/x", "headers": headers, "query_string": b""}
    asyncio.run(app(scope, receive, send))
    start = next(m for m in sent if m["type"] == "http.response.start")
    return start["status"]


async def _reads_everything(scope, receive, send):
    """A stand-in app that consumes the body, then answers 200."""
    while True:
        message = await receive()
        if message["type"] != "http.request" or not message.get("more_body"):
            break
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


class TestBodySizeLimit:
    def guard(self):
        return BodySizeLimitMiddleware(_reads_everything, max_upload_bytes=1000, max_body_bytes=100)

    def test_declared_oversize_is_refused_without_reading(self):
        status = _run(self.guard(), headers=[(b"content-type", b"multipart/form-data; boundary=x"),
                                              (b"content-length", b"5000")], chunks=[b""])
        assert status == 413

    def test_undeclared_oversize_is_cut_off_while_streaming(self):
        status = _run(self.guard(), headers=[(b"content-type", b"application/json")],
                      chunks=[b"a" * 60, b"a" * 60, b"a" * 60])
        assert status == 413

    def test_bodies_within_the_limit_pass_through(self):
        assert _run(self.guard(), headers=[(b"content-type", b"application/json"), (b"content-length", b"50")],
                    chunks=[b"a" * 50]) == 200
        assert _run(self.guard(), headers=[(b"content-type", b"multipart/form-data; boundary=x")],
                    chunks=[b"a" * 400, b"a" * 400]) == 200

    def test_an_oversized_upload_gets_the_error_envelope(self, client, auth):
        from truthshield.settings import get_settings

        too_big = b"%PDF-1.4\n" + b"0" * (get_settings().max_upload_bytes + 2 * 1024 * 1024)
        response = client.post("/api/v1/investigations/upload", headers=auth,
                               files={"file": ("big.pdf", too_big, "application/pdf")})
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
        assert response.headers.get("X-Request-ID")


class TestCors:
    def test_patch_is_allowed_for_the_admin_endpoints(self, client):
        response = client.options(
            "/api/v1/sources/00000000-0000-0000-0000-000000000000",
            headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "PATCH",
                     "Access-Control-Request-Headers": "authorization,content-type"},
        )
        assert response.status_code == 200
        assert "PATCH" in response.headers["access-control-allow-methods"]


class TestRateLimitKey:
    """Limits count per account when the caller is signed in, per address otherwise."""

    @staticmethod
    def _request(authorization=None):
        from types import SimpleNamespace

        headers = {"authorization": authorization} if authorization else {}
        return SimpleNamespace(headers=headers)

    def test_a_signed_in_caller_is_keyed_by_account(self, client):
        from truthshield.api.limits import client_key
        from truthshield.services import auth

        token = client.post("/api/v1/auth/signup", json={
            "email": f"rl{__import__('uuid').uuid4().hex[:10]}@example.com", "password": "correct-horse-42",
        }).json()["access_token"]
        subject = auth.decode_token(token)["sub"]
        assert client_key(self._request(f"Bearer {token}"), lambda r: "ip") == f"user:{subject}"

    def test_a_forged_or_missing_token_falls_back_to_the_address(self):
        from truthshield.api.limits import client_key

        assert client_key(self._request("Bearer not.a.real.token"), lambda r: "1.2.3.4") == "1.2.3.4"
        assert client_key(self._request(), lambda r: "1.2.3.4") == "1.2.3.4"
