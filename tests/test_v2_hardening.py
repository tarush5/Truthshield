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


class TestExportPrivacy:
    SECRETS = {"otp": "482913", "phone": "9876543210", "upi": "victim.name@okhdfcbank", "acct": "123456789012"}

    def test_exports_mask_personal_data_but_keep_identifiers(self, client, auth):
        s = self.SECRETS
        text = (f"Your SBI account {s['acct']} is blocked. Your OTP is {s['otp']}, share it with our officer "
                f"on {s['phone']} or pay {s['upi']} now http://sbi-kyc.xyz/login")
        inv = client.post("/api/v1/investigations", headers=auth, json={"type": "message", "content": text}).json()
        as_json = client.get(f"/api/v1/investigations/{inv['id']}/export?format=json", headers=auth)
        as_csv = client.get(f"/api/v1/investigations/{inv['id']}/export?format=csv", headers=auth).text
        for name, value in s.items():
            assert value not in as_json.text, f"{name} leaked into the JSON export"
            assert value not in as_csv, f"{name} leaked into the CSV export"
        body = as_json.json()
        # Identifiers survive untouched (a public id has ten digits).
        assert body["public_id"] == inv["public_id"] and body["id"] == inv["id"]
        assert body["input_sha256"] and len(body["input_sha256"]) == 64

    def test_the_list_excerpt_masks_upi_ids(self, client, auth):
        client.post("/api/v1/investigations", headers=auth,
                    json={"type": "message", "content": "Send the refund fee to victim.name@okhdfcbank today please"})
        assert "victim.name@okhdfcbank" not in client.get("/api/v1/investigations", headers=auth).text


class TestUpiRedaction:
    def test_upi_ids_are_masked(self):
        from truthshield.fraud.privacy import redact

        text, found = redact("Pay to rahul.sharma@okaxis or 9876543210@ybl today")
        assert "rahul.sharma@okaxis" not in text and "@okaxis" in text
        assert {r.kind for r in found} >= {"upi"}

    def test_emails_and_ordinary_text_are_unaffected_by_the_upi_rule(self):
        from truthshield.fraud.privacy import redact

        _, found = redact("Write to support@example.com about order 4471")
        assert [r.kind for r in found] == ["email"]
        assert redact("Meet at 5pm @ the library")[1] == []
