"""
Security regression tests.

Each class corresponds to a finding from the audit. The comments record what
the exploit actually was, so a future change that reopens one of these is
recognisable as a regression rather than a puzzling assertion.
"""

import time

import pytest

from backend.security import BlockedURLError, assert_url_is_public


# ═══════════════════════════════════════════════
# SSRF — /analyze fetches caller-supplied URLs
# ═══════════════════════════════════════════════

class TestSSRFGuard:
    """
    `POST /analyze` takes a `url`, fetches it server-side, and returns the page
    body to the caller as `original_text`. Unguarded, that is a full-read SSRF:
    the caller reads anything the server can reach.
    """

    @pytest.mark.parametrize("url", [
        "http://169.254.169.254/latest/meta-data/iam/security-credentials/",  # AWS
        "http://100.100.100.200/latest/meta-data/",                          # Alibaba
        "http://metadata.google.internal/computeMetadata/v1/",               # GCP
    ])
    def test_cloud_metadata_is_blocked(self, url):
        with pytest.raises(BlockedURLError):
            assert_url_is_public(url)

    @pytest.mark.parametrize("url", [
        "http://127.0.0.1:8000/api/v1/organizations",
        "http://localhost:6379/",
        "http://10.0.0.5/admin",
        "http://192.168.1.1/",
        "http://172.16.0.1/",
        "http://[::1]:8000/",
        "http://0.0.0.0:8000/",
    ])
    def test_internal_addresses_are_blocked(self, url):
        with pytest.raises(BlockedURLError):
            assert_url_is_public(url)

    @pytest.mark.parametrize("url", [
        "file:///etc/passwd",
        "gopher://127.0.0.1:6379/_SET%20x%20y",
        "ftp://internal.example.com/",
        "data:text/html,<script>alert(1)</script>",
    ])
    def test_non_http_schemes_are_blocked(self, url):
        with pytest.raises(BlockedURLError):
            assert_url_is_public(url)

    def test_decimal_and_hex_loopback_forms_are_blocked(self):
        # 2130706433 == 0x7f000001 == 127.0.0.1. Blocking the dotted form alone
        # is not enough; these parse to the same address.
        for host in ("http://2130706433/", "http://0x7f000001/"):
            with pytest.raises(BlockedURLError):
                assert_url_is_public(host)

    def test_public_urls_are_allowed(self):
        assert assert_url_is_public("https://www.reuters.com/world/") is not None
        assert assert_url_is_public("http://example.com/article") is not None

    def test_error_message_does_not_echo_internal_addresses(self):
        """
        The refusal itself must not become the leak. Naming the resolved
        address would confirm what lives on the internal network.
        """
        with pytest.raises(BlockedURLError) as exc:
            assert_url_is_public("http://10.1.2.3/secret")
        assert "10.1.2.3" not in str(exc.value)


# ═══════════════════════════════════════════════
# Fail-closed configuration
# ═══════════════════════════════════════════════

class TestConfigurationFailsClosed:
    """
    APP_ENV gates the anonymous-guest fallback, and JWT_SECRET_KEY signs every
    session token. Both previously defaulted to the permissive value, so a
    deployment that set neither came up wide open with only a log line to say so.
    """

    def test_app_env_defaults_to_production(self):
        # Checks the declared field default, not an instantiated Settings:
        # Settings reads a local .env, so instantiating here would assert on
        # whatever the developer's machine happens to have configured.
        from backend.config import Settings
        assert Settings.model_fields["APP_ENV"].default == "production"

    def test_default_jwt_secret_is_fatal_outside_development(self):
        from backend.config import Settings
        with pytest.raises(Exception) as exc:
            Settings(APP_ENV="production", JWT_SECRET_KEY="change-me-in-production")
        assert "JWT_SECRET_KEY" in str(exc.value)

    def test_empty_jwt_secret_is_fatal_outside_development(self):
        from backend.config import Settings
        with pytest.raises(Exception):
            Settings(APP_ENV="production", JWT_SECRET_KEY="")

    def test_default_jwt_secret_is_tolerated_in_development(self):
        from backend.config import Settings
        s = Settings(APP_ENV="development", JWT_SECRET_KEY="change-me-in-production")
        assert s.APP_ENV == "development"

    def test_wildcard_cors_is_rejected(self):
        """
        The app sends Authorization headers with allow_credentials=True, and a
        wildcard origin cannot be combined with that.
        """
        from backend.config import Settings
        with pytest.raises(Exception) as exc:
            Settings(JWT_SECRET_KEY="x" * 64, CORS_ORIGINS="https://app.example.com,*")
        assert "CORS_ORIGINS" in str(exc.value)


# ═══════════════════════════════════════════════
# OTP login
# ═══════════════════════════════════════════════

class TestOTPVerification:
    """
    /auth/verify accepted the literal code "123456" for any address, in every
    environment, which minted a valid session for an arbitrary account.
    """

    @pytest.fixture(autouse=True)
    def _clear_store(self):
        from backend.api import routes
        routes.otp_store.clear()
        yield
        routes.otp_store.clear()

    def _verify(self, email, token):
        import asyncio
        from backend.api import routes
        return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            routes.verify_otp({"email": email, "token": token}, db=None)
        )

    def test_magic_code_no_longer_works(self):
        from fastapi import HTTPException
        from backend.api import routes
        routes.otp_store["victim@example.com"] = ("999111", time.time(), 0)
        with pytest.raises(HTTPException) as exc:
            self._verify("victim@example.com", "123456")
        assert exc.value.status_code == 400

    def test_unknown_email_is_rejected(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            self._verify("nobody@example.com", "123456")

    def test_expired_code_is_rejected(self):
        from fastapi import HTTPException
        from backend.api import routes
        issued = time.time() - (routes.OTP_TTL_SECONDS + 1)
        routes.otp_store["a@example.com"] = ("123456", issued, 0)
        with pytest.raises(HTTPException):
            self._verify("a@example.com", "123456")

    def test_attempts_are_capped(self):
        from fastapi import HTTPException
        from backend.api import routes
        routes.otp_store["a@example.com"] = ("999999", time.time(), 0)
        for _ in range(routes.OTP_MAX_ATTEMPTS):
            with pytest.raises(HTTPException):
                self._verify("a@example.com", "000000")
        # The record is dropped once the cap is hit, so the correct code is
        # useless too — the attacker cannot simply keep guessing.
        with pytest.raises(HTTPException):
            self._verify("a@example.com", "999999")

    def test_codes_are_generated_with_a_cryptographic_rng(self):
        """random.randint is predictable from prior outputs; these are auth material."""
        import inspect
        from backend.api import routes
        src = inspect.getsource(routes.send_otp)
        assert "secrets.randbelow" in src
        assert "random.randint" not in src


# ═══════════════════════════════════════════════
# JWT verification
# ═══════════════════════════════════════════════

class TestTokenSignatureIsVerified:
    """
    Both get_current_user and /auth/oauth-verify decoded RS/ES/PS-signed tokens
    with verify_signature disabled "to avoid PEM loading errors", so a token
    forged with the attacker's own key was accepted as genuine.
    """

    def test_no_code_path_disables_signature_verification(self):
        # Parsed rather than grepped: the comments in these modules describe
        # the removed bypass and would match a plain substring search.
        import ast
        import inspect
        from backend.api import auth as auth_mod
        from backend.api import routes as routes_mod

        for module in (auth_mod, routes_mod):
            tree = ast.parse(inspect.getsource(module))
            literals = {
                node.value
                for node in ast.walk(tree)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
            }
            offenders = {lit for lit in literals if "verify_signature" in lit}
            assert not offenders, (
                f"{module.__name__} still references verify_signature in code: {offenders}"
            )

    def test_asymmetric_tokens_are_rejected_not_trusted(self):
        import inspect
        from backend.api import auth as auth_mod
        src = inspect.getsource(auth_mod.get_current_user)
        # Only symmetric algorithms are accepted against a shared secret.
        assert 'alg.startswith("HS")' in src

    def test_oauth_verify_requires_a_configured_secret(self):
        """
        Without SUPABASE_JWT_SECRET the endpoint skipped verification entirely
        and trusted a caller-supplied email — account takeover for any address.
        """
        import inspect
        from backend.api import routes
        src = inspect.getsource(routes.oauth_verify)
        assert "if not settings.SUPABASE_JWT_SECRET" in src
        # Identity must come from the token, never from the request body.
        assert 'email = token_payload.get("email")' in src


# ═══════════════════════════════════════════════
# Resource limits
# ═══════════════════════════════════════════════

class TestResourceLimits:
    def test_upload_size_limit_is_enforced(self):
        """
        MAX_UPLOAD_SIZE_MB was defined in config and consulted nowhere; the
        handler did `await file.read()`, pulling an entire upload into memory
        before any size check.
        """
        import inspect
        from backend.api import routes
        src = inspect.getsource(routes.analyze_content)
        assert "max_upload_bytes" in src
        assert "413" in src

    def test_rate_limiting_middleware_is_installed(self):
        """
        slowapi's default_limits apply only to decorated routes unless
        SlowAPIMiddleware is added. Without it every endpoint was unlimited
        while the startup log claimed rate limiting was enabled.
        """
        import inspect
        from backend import main
        src = inspect.getsource(main)
        assert "SlowAPIMiddleware" in src
        assert "add_middleware(SlowAPIMiddleware)" in src


# ═══════════════════════════════════════════════
# Report access control
# ═══════════════════════════════════════════════

class TestReportAccessControl:
    def test_report_endpoint_takes_an_identity(self):
        """
        GET /report/{id} took no identity at all, so anyone holding an id —
        from a shared link, a proxy log, a browser history — could read another
        workspace's analysis in full.
        """
        import inspect
        from backend.api import routes
        sig = inspect.signature(routes.get_report)
        assert "current_user" in sig.parameters

    def test_unauthorised_access_is_a_404_not_a_403(self):
        """403 would confirm the id exists, which is itself information."""
        import inspect
        from backend.api import routes
        src = inspect.getsource(routes.get_report)
        assert "404" in src
