"""
Security regression tests for the rewritten backend.

Each case records the exploit it prevents, so a change that reopens one is
recognisable as a regression rather than a puzzling assertion.
"""

import pytest

from truthshield.security import BlockedURLError, assert_url_is_public


class TestSSRFGuard:
    """
    /analyze fetches a caller-supplied URL and returns the page body in the
    report. Unguarded that is a full-read SSRF: the caller reads whatever the
    server can reach.
    """

    @pytest.mark.parametrize("url", [
        "http://169.254.169.254/latest/meta-data/iam/security-credentials/",   # AWS
        "http://100.100.100.200/latest/meta-data/",                           # Alibaba
        "http://metadata.google.internal/computeMetadata/v1/",                # GCP
    ])
    def test_cloud_metadata_is_blocked(self, url):
        with pytest.raises(BlockedURLError):
            assert_url_is_public(url)

    @pytest.mark.parametrize("url", [
        "http://127.0.0.1:8000/api/v1/health",
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

    def test_alternate_loopback_encodings_are_blocked(self):
        # 2130706433 == 0x7f000001 == 127.0.0.1; blocking the dotted form alone
        # is not enough, since these parse to the same address.
        for host in ("http://2130706433/", "http://0x7f000001/"):
            with pytest.raises(BlockedURLError):
                assert_url_is_public(host)

    def test_public_urls_pass(self):
        assert assert_url_is_public("https://www.reuters.com/world/")
        assert assert_url_is_public("http://example.com/article")

    def test_the_refusal_does_not_echo_the_internal_address(self):
        """Naming the address would confirm what lives on the private network."""
        with pytest.raises(BlockedURLError) as exc:
            assert_url_is_public("http://10.1.2.3/secret")
        assert "10.1.2.3" not in str(exc.value)


class TestConfigurationFailsClosed:
    """
    APP_ENV gated an anonymous-guest fallback and JWT_SECRET_KEY signs every
    session token. Both defaulted to the permissive value, so a deployment
    that set neither came up open with only a log line to say so.
    """

    def test_app_env_defaults_to_production(self):
        from truthshield.settings import Environment, Settings
        assert Settings.model_fields["APP_ENV"].default is Environment.PRODUCTION

    def test_placeholder_secret_is_fatal_in_production(self):
        from truthshield.settings import Settings
        with pytest.raises(Exception) as exc:
            Settings(APP_ENV="production", JWT_SECRET_KEY="change-me-in-production",
                     DATABASE_URL="postgresql://u:p@localhost/db")
        assert "JWT_SECRET_KEY" in str(exc.value)

    def test_short_secret_is_rejected(self):
        from truthshield.settings import Settings
        with pytest.raises(Exception):
            Settings(APP_ENV="production", JWT_SECRET_KEY="too-short",
                     DATABASE_URL="postgresql://u:p@localhost/db")

    def test_sqlite_is_refused_in_production(self):
        """
        The previous version fell back to a local SQLite file whenever
        Postgres was unreachable, so an outage looked like a working service
        that had quietly lost every report.
        """
        from truthshield.settings import Settings
        with pytest.raises(Exception) as exc:
            Settings(APP_ENV="production", JWT_SECRET_KEY="x" * 48,
                     DATABASE_URL="sqlite:///./local.db")
        assert "SQLite" in str(exc.value)

    def test_wildcard_cors_is_rejected(self):
        from truthshield.settings import Settings
        with pytest.raises(Exception) as exc:
            Settings(JWT_SECRET_KEY="x" * 48, CORS_ORIGINS="https://app.example.com,*",
                     DATABASE_URL="postgresql://u:p@localhost/db")
        assert "CORS_ORIGINS" in str(exc.value)


class TestTokenVerification:
    def test_asymmetric_algorithms_are_rejected_not_trusted(self):
        """
        Both entry points previously decoded RS/ES/PS tokens with signature
        verification disabled, so a token forged with the attacker's own key
        was accepted as genuine.
        """
        import ast
        import inspect
        from truthshield.services import auth

        tree = ast.parse(inspect.getsource(auth))
        literals = {
            node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        assert not any("verify_signature" in s for s in literals)

    def test_decode_rejects_a_token_signed_with_another_key(self):
        from jose import jwt
        from truthshield.services.auth import decode_token
        forged = jwt.encode({"sub": "x", "email": "a@example.com"},
                            "not-the-signing-key", algorithm="HS256")
        assert decode_token(forged) is None

    def test_decode_rejects_alg_none(self):
        import base64
        import json
        from truthshield.services.auth import decode_token

        def b64(obj):
            return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()

        token = f"{b64({'alg': 'none'})}.{b64({'sub': 'x', 'email': 'a@example.com'})}."
        assert decode_token(token) is None


class TestPasswordHandling:
    def test_passwords_are_slow_hashed_and_salted(self):
        from truthshield.services.auth import hash_password
        a, b = hash_password("same-password"), hash_password("same-password")
        assert a != b, "each hash must use a fresh salt"
        assert a.startswith("pbkdf2_sha256$")
        assert int(a.split("$")[1]) >= 200_000

    def test_verification_handles_a_missing_hash(self):
        from truthshield.services.auth import hash_password, verify_password
        stored = hash_password("correct-horse-42")
        assert verify_password("correct-horse-42", stored) is True
        assert verify_password("wrong", stored) is False
        # No stored hash still runs the derivation, so a missing account and a
        # wrong password cannot be told apart by timing.
        assert verify_password("anything", None) is False


class TestAPIKeys:
    def test_only_a_digest_is_stored(self, session):
        """The raw key is shown once and never persisted."""
        import uuid as _uuid
        from truthshield.infra.models import Organization, User
        from truthshield.services.auth import generate_api_key

        user = User(email=f"k{_uuid.uuid4().hex[:8]}@example.com")
        session.add(user)
        session.flush()
        org = Organization(name="w", owner_id=user.id)
        session.add(org)
        session.flush()

        record, raw = generate_api_key(session, org.id, "test", user.id)
        assert raw.startswith("ts_")
        assert record.key_hash != raw
        assert len(record.key_hash) == 64            # sha256 hex
        assert raw not in record.key_hash


# ═══════════════════════════════════════════════
# Configuration that must agree across the stack
# ═══════════════════════════════════════════════

class TestFrontendBackendAgreement:
    """
    The frontend is a separate build with its own copy of the API location.
    Nothing in either language catches the two drifting apart, and when they
    did — the backend on 8000, the frontend calling 8100 — every request
    failed with a connection error that presented as a broken login.
    """

    def _repo_root(self):
        from pathlib import Path
        return Path(__file__).resolve().parent.parent

    def test_frontend_default_api_port_matches_the_backend(self):
        import re
        from truthshield.settings import Settings

        source = (self._repo_root() / "frontend" / "src" / "lib" / "api.js").read_text(encoding="utf-8")
        match = re.search(r"const DEFAULT_BASE = 'http://127\.0\.0\.1:(\d+)/api/v1';", source)
        assert match, "Could not find DEFAULT_BASE in frontend/src/lib/api.js"

        assert int(match.group(1)) == Settings.model_fields["APP_PORT"].default

    def test_vite_dev_proxy_targets_the_same_port(self):
        import re
        from truthshield.settings import Settings

        source = (self._repo_root() / "frontend" / "vite.config.js").read_text(encoding="utf-8")
        match = re.search(r"target: 'http://127\.0\.0\.1:(\d+)'", source)
        assert match, "Could not find the dev proxy target in frontend/vite.config.js"

        assert int(match.group(1)) == Settings.model_fields["APP_PORT"].default

    def test_env_example_starts_a_fresh_checkout(self):
        """
        `cp .env.example .env` has to be enough to run locally. It previously
        pointed DATABASE_URL at Postgres, so a first-time reader following the
        README hit a connection error before reaching the app.
        """
        text = (self._repo_root() / ".env.example").read_text(encoding="utf-8")
        active = [
            line.strip() for line in text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        settings_lines = dict(
            line.split("=", 1) for line in active if "=" in line
        )
        assert settings_lines.get("APP_ENV") == "development"
        assert settings_lines.get("DATABASE_URL", "").startswith("sqlite")
