"""
API behaviour, exercised through the real app.

These go through TestClient rather than calling handlers directly, so the
dependency graph — auth resolution, session handling, validation — is part of
what is being tested.
"""

import uuid

import pytest


# ══════════════════════════════════════════════════════════════
# Auth
# ══════════════════════════════════════════════════════════════

class TestSignup:
    def test_creates_an_account_and_returns_a_token(self, client):
        email = f"u{uuid.uuid4().hex[:10]}@example.com"
        r = client.post("/api/v1/auth/signup", json={"email": email, "password": "correct-horse-42"})
        assert r.status_code == 201
        body = r.json()
        assert body["token_type"] == "bearer"
        assert body["user"]["email"] == email
        assert body["user"]["org_id"], "every user should get a workspace"

    def test_duplicate_registration_does_not_confirm_the_address(self, client):
        """
        Signing up twice must not reveal that the first attempt succeeded —
        otherwise this endpoint enumerates registered users.
        """
        email = f"u{uuid.uuid4().hex[:10]}@example.com"
        client.post("/api/v1/auth/signup", json={"email": email, "password": "correct-horse-42"})
        r = client.post("/api/v1/auth/signup", json={"email": email, "password": "correct-horse-42"})
        assert r.status_code == 400
        assert "already" not in r.text.lower()
        assert "exists" not in r.text.lower()

    @pytest.mark.parametrize("password", [
        "short",              # below the length floor
        "12345678901234",     # digits only
        "abcdefghijklmn",     # letters only
    ])
    def test_weak_passwords_are_rejected(self, client, password):
        r = client.post("/api/v1/auth/signup", json={
            "email": f"u{uuid.uuid4().hex[:8]}@example.com", "password": password,
        })
        assert r.status_code == 422


class TestSignin:
    def test_correct_credentials_return_a_token(self, client):
        email = f"u{uuid.uuid4().hex[:10]}@example.com"
        client.post("/api/v1/auth/signup", json={"email": email, "password": "correct-horse-42"})
        r = client.post("/api/v1/auth/signin", json={"email": email, "password": "correct-horse-42"})
        assert r.status_code == 200
        assert r.json()["access_token"]

    def test_wrong_password_and_unknown_account_are_indistinguishable(self, client):
        """
        Same status and same message either way. A different response for an
        unknown address turns the login form into an account oracle.
        """
        email = f"u{uuid.uuid4().hex[:10]}@example.com"
        client.post("/api/v1/auth/signup", json={"email": email, "password": "correct-horse-42"})

        wrong = client.post("/api/v1/auth/signin", json={"email": email, "password": "not-the-password"})
        missing = client.post("/api/v1/auth/signin", json={
            "email": f"nobody{uuid.uuid4().hex[:8]}@example.com", "password": "not-the-password",
        })
        assert wrong.status_code == missing.status_code == 401
        assert wrong.json()["detail"] == missing.json()["detail"]


class TestOTP:
    def test_requesting_a_code_never_reveals_whether_the_account_exists(self, client):
        known = client.post("/api/v1/auth/otp", json={"email": "someone@example.com"})
        unknown = client.post("/api/v1/auth/otp", json={"email": "nobody-at-all@example.com"})
        assert known.status_code == unknown.status_code == 200
        assert known.json() == unknown.json()

    def test_there_is_no_magic_code(self, client):
        """
        The previous implementation accepted the literal "123456" for any
        address, in every environment — a backdoor into any account.
        """
        client.post("/api/v1/auth/otp", json={"email": "victim@example.com"})
        r = client.post("/api/v1/auth/otp/verify", json={"email": "victim@example.com", "code": "123456"})
        assert r.status_code == 400

    def test_a_valid_code_signs_the_user_in(self, client, monkeypatch):
        from truthshield.services import auth
        issued = {}

        real_issue = auth.OTPStore.issue

        def capture(self, email):
            code = real_issue(self, email)
            issued[email] = code
            return code

        monkeypatch.setattr(auth.OTPStore, "issue", capture)

        email = f"u{uuid.uuid4().hex[:10]}@example.com"
        client.post("/api/v1/auth/otp", json={"email": email})
        r = client.post("/api/v1/auth/otp/verify", json={"email": email, "code": issued[email]})
        assert r.status_code == 200
        assert r.json()["access_token"]

    def test_a_code_cannot_be_reused(self, client, monkeypatch):
        from truthshield.services import auth
        issued = {}
        real_issue = auth.OTPStore.issue

        def capture(self, email):
            code = real_issue(self, email)
            issued[email] = code
            return code

        monkeypatch.setattr(auth.OTPStore, "issue", capture)

        email = f"u{uuid.uuid4().hex[:10]}@example.com"
        client.post("/api/v1/auth/otp", json={"email": email})
        code = issued[email]
        assert client.post("/api/v1/auth/otp/verify", json={"email": email, "code": code}).status_code == 200
        assert client.post("/api/v1/auth/otp/verify", json={"email": email, "code": code}).status_code == 400


class TestTokens:
    def test_me_requires_authentication(self, client):
        assert client.get("/api/v1/auth/me").status_code == 401

    def test_me_returns_the_caller(self, client, auth):
        r = client.get("/api/v1/auth/me", headers=auth)
        assert r.status_code == 200
        assert "@example.com" in r.json()["email"]

    def test_a_forged_token_is_rejected(self, client):
        """Signed with the wrong key — the signature must actually be checked."""
        from jose import jwt
        forged = jwt.encode(
            {"sub": str(uuid.uuid4()), "email": "attacker@example.com"},
            "not-the-real-signing-key", algorithm="HS256",
        )
        r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"})
        assert r.status_code == 401

    def test_an_unsigned_token_is_rejected(self, client):
        """`alg: none` must never be honoured."""
        import base64, json

        def b64(payload):
            return base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()

        token = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': str(uuid.uuid4()), 'email': 'a@example.com'})}."
        r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


# ══════════════════════════════════════════════════════════════
# Analysis
# ══════════════════════════════════════════════════════════════

class TestAnalyzeValidation:
    def test_requires_authentication(self, client):
        """
        There is no anonymous-guest fallback. The previous version provisioned
        one whenever APP_ENV was 'development' — its default value.
        """
        assert client.post("/api/v1/analyze", data={"text": "hello"}).status_code == 401

    def test_rejects_an_empty_submission(self, client, auth):
        r = client.post("/api/v1/analyze", data={"language": "en"}, headers=auth)
        assert r.status_code == 400

    @pytest.mark.parametrize("url", [
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1:8000/api/v1/health",
        "http://10.0.0.1/",
        "file:///etc/passwd",
    ])
    def test_rejects_urls_that_would_be_ssrf(self, client, auth, url):
        r = client.post("/api/v1/analyze", data={"url": url}, headers=auth)
        assert r.status_code == 400

    def test_rejects_oversized_text(self, client, auth):
        from truthshield.settings import get_settings
        too_long = "x" * (get_settings().MAX_TEXT_LENGTH + 1)
        r = client.post("/api/v1/analyze", data={"text": too_long}, headers=auth)
        assert r.status_code == 413

    def test_rejects_a_dangerous_file_extension(self, client, auth):
        r = client.post(
            "/api/v1/analyze",
            files={"file": ("evil.tar.gz.../../x", b"data", "application/octet-stream")},
            headers=auth,
        )
        assert r.status_code in (400, 422)


class TestReportAccessControl:
    def _make_report(self, client, headers):
        r = client.post("/api/v1/analyze", data={"text": "Paris is the capital of France."}, headers=headers)
        assert r.status_code == 200, r.text
        return r.json()["id"]

    def test_owner_can_read_their_report(self, client, auth):
        report_id = self._make_report(client, auth)
        assert client.get(f"/api/v1/reports/{report_id}", headers=auth).status_code == 200

    def test_a_stranger_cannot_read_it(self, client, auth):
        """
        404, not 403: a 403 would confirm the id exists. The previous endpoint
        took no identity at all, so any id was readable by anyone.
        """
        report_id = self._make_report(client, auth)

        other = client.post("/api/v1/auth/signup", json={
            "email": f"u{uuid.uuid4().hex[:10]}@example.com", "password": "correct-horse-42",
        }).json()["access_token"]

        r = client.get(f"/api/v1/reports/{report_id}", headers={"Authorization": f"Bearer {other}"})
        assert r.status_code == 404

    def test_anonymous_cannot_read_it(self, client, auth):
        report_id = self._make_report(client, auth)
        assert client.get(f"/api/v1/reports/{report_id}").status_code == 404

    def test_listing_only_returns_your_own(self, client, auth):
        self._make_report(client, auth)
        other = client.post("/api/v1/auth/signup", json={
            "email": f"u{uuid.uuid4().hex[:10]}@example.com", "password": "correct-horse-42",
        }).json()["access_token"]

        mine = client.get("/api/v1/reports", headers=auth).json()
        theirs = client.get("/api/v1/reports", headers={"Authorization": f"Bearer {other}"}).json()
        assert len(mine) >= 1
        assert theirs == []


class TestReportShape:
    def test_report_states_what_it_could_not_check(self, client, auth):
        r = client.post("/api/v1/analyze", data={"text": "Paris is the capital of France."}, headers=auth)
        body = r.json()

        # Every detector carries whether it actually contributed.
        assert body["detectors"], "detectors should be reported even when not applicable"
        for d in body["detectors"]:
            assert "status" in d and "counted_toward_score" in d
            if d["status"] != "ok":
                assert d["counted_toward_score"] is False

        assert set(body["breakdown"]) == {
            "fact_match", "source_credibility", "evidence_strength", "manipulation_risk",
        }
        assert 0 <= body["trust_score"] <= 100
        assert 0 <= body["fake_probability"] <= 100


# ══════════════════════════════════════════════════════════════
# Meta
# ══════════════════════════════════════════════════════════════

class TestMeta:
    def test_health_reports_real_capabilities(self, client):
        """
        /health must say which detectors can actually run, so a missing model
        is visible to an operator rather than inferred from clean results.
        """
        body = client.get("/api/v1/health").json()
        assert body["version"]
        assert isinstance(body["database"], bool)
        caps = body["capabilities"]
        for key in ("torch", "opencv", "tesseract_ocr", "librosa"):
            assert isinstance(caps[key], bool)

    def test_stats_are_public_and_well_formed(self, client):
        body = client.get("/api/v1/stats").json()
        assert body["total_analyses"] >= 0
        assert isinstance(body["verdicts"], dict)

    def test_unhandled_errors_do_not_leak_internals(self, client, monkeypatch):
        """
        The previous API returned exception text in `detail`, which described
        the token verification setup to anyone sending a malformed token.
        """
        from truthshield.api import routes
        monkeypatch.setattr(
            routes, "stats",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("secret internal detail")),
        )
        r = client.get("/api/v1/stats")
        assert "secret internal detail" not in r.text
