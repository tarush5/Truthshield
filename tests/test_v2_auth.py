"""
2.0 sessions and access control: refresh-token rotation and reuse detection,
logout, lockout, roles, admin, audit, and the auth rate limit being attached.
"""

import uuid

import pytest

PASSWORD = "correct-horse-42"


def signup(client, email=None):
    email = email or f"a{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/api/v1/auth/signup", json={"email": email, "password": PASSWORD})
    assert r.status_code == 201, r.text
    return email, r.json()


class TestRefresh:
    def test_signup_returns_a_refresh_token_and_role(self, client):
        _, body = signup(client)
        assert body["refresh_token"].startswith("tsr_") and body["user"]["role"] == "USER"

    def test_rotation_issues_a_new_pair_and_spends_the_old_token(self, client):
        _, body = signup(client)
        first = body["refresh_token"]
        r = client.post("/api/v1/auth/refresh", json={"refresh_token": first})
        assert r.status_code == 200
        second = r.json()["refresh_token"]
        assert second != first and r.json()["access_token"]

        again = client.post("/api/v1/auth/refresh", json={"refresh_token": first})
        assert again.status_code == 401 and again.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"

    def test_reuse_revokes_the_whole_family(self, client):
        _, body = signup(client)
        stolen = body["refresh_token"]
        legit = client.post("/api/v1/auth/refresh", json={"refresh_token": stolen}).json()["refresh_token"]
        client.post("/api/v1/auth/refresh", json={"refresh_token": stolen})          # replay
        assert client.post("/api/v1/auth/refresh", json={"refresh_token": legit}).status_code == 401

    def test_tokens_are_stored_hashed(self, client, session):
        from truthshield.infra.models import RefreshToken
        _, body = signup(client)
        raw = body["refresh_token"]
        assert session.query(RefreshToken).filter(RefreshToken.token_hash == raw).count() == 0

    def test_logout_revokes(self, client):
        _, body = signup(client)
        assert client.post("/api/v1/auth/logout", json={"refresh_token": body["refresh_token"]}).status_code == 204
        assert client.post("/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]}).status_code == 401

    def test_logout_with_an_unknown_token_is_silent(self, client):
        r = client.post("/api/v1/auth/logout", json={"refresh_token": "tsr_" + "x" * 40})
        assert r.status_code == 204


class TestLockout:
    def test_repeated_failures_lock_the_address(self, client):
        from truthshield.settings import get_settings
        email, _ = signup(client)
        for _ in range(get_settings().LOGIN_MAX_FAILURES):
            assert client.post("/api/v1/auth/signin", json={"email": email, "password": "wrong-pass-1"}).status_code == 401
        locked = client.post("/api/v1/auth/signin", json={"email": email, "password": PASSWORD})
        assert locked.status_code == 429 and locked.json()["error"]["code"] == "ACCOUNT_LOCKED"

    def test_lockout_looks_the_same_for_unregistered_addresses(self, client):
        from truthshield.settings import get_settings
        email = f"ghost{uuid.uuid4().hex[:8]}@example.com"
        for _ in range(get_settings().LOGIN_MAX_FAILURES):
            client.post("/api/v1/auth/signin", json={"email": email, "password": "wrong-pass-1"})
        r = client.post("/api/v1/auth/signin", json={"email": email, "password": "wrong-pass-1"})
        assert r.status_code == 429 and r.json()["error"]["code"] == "ACCOUNT_LOCKED"

    def test_success_clears_the_counter(self, client):
        email, _ = signup(client)
        for _ in range(2):
            client.post("/api/v1/auth/signin", json={"email": email, "password": "wrong-pass-1"})
        assert client.post("/api/v1/auth/signin", json={"email": email, "password": PASSWORD}).status_code == 200


@pytest.fixture
def admin(client, monkeypatch):
    from truthshield.settings import get_settings
    email = f"admin{uuid.uuid4().hex[:8]}@example.com"
    monkeypatch.setattr(get_settings(), "BOOTSTRAP_ADMIN_EMAILS", email)
    _, body = signup(client, email)
    assert body["user"]["role"] == "ADMIN"
    return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]["id"]


class TestRoles:
    def test_regular_users_cannot_reach_admin_routes(self, client, auth):
        r = client.get("/api/v1/admin/users", headers=auth)
        assert r.status_code == 403 and r.json()["error"]["code"] == "FORBIDDEN"

    def test_admin_can_change_roles_and_it_is_audited(self, client, admin, session):
        from truthshield.infra.models import AuditLog
        headers, _ = admin
        _, target = signup(client)
        r = client.patch(f"/api/v1/admin/users/{target['user']['id']}", json={"role": "ANALYST"}, headers=headers)
        assert r.status_code == 200 and r.json()["role"] == "ANALYST"

        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {target['access_token']}"}).json()
        assert me["role"] == "ANALYST", "role is read from the database, not the old token"

        assert session.query(AuditLog).filter(AuditLog.action == "admin.user.update").count() >= 1

    def test_admin_cannot_demote_themselves(self, client, admin):
        headers, admin_id = admin
        r = client.patch(f"/api/v1/admin/users/{admin_id}", json={"role": "USER"}, headers=headers)
        assert r.status_code == 400

    def test_deactivated_user_loses_access_immediately(self, client, admin):
        headers, _ = admin
        _, target = signup(client)
        client.patch(f"/api/v1/admin/users/{target['user']['id']}", json={"is_active": False}, headers=headers)
        r = client.get("/api/v1/investigations", headers={"Authorization": f"Bearer {target['access_token']}"})
        assert r.status_code == 401

    def test_admin_sees_every_investigation(self, client, admin, auth):
        headers, _ = admin
        created = client.post("/api/v1/investigations", json={"type": "text", "content": "admin visibility"},
                              headers=auth).json()
        assert client.get(f"/api/v1/investigations/{created['id']}", headers=headers).status_code == 200
        # ...but not the original content of someone else's submission? Admins do see it,
        # because they handle abuse reports; that is documented in docs/DATABASE.md.


class TestAudit:
    def test_signin_and_investigations_are_audited(self, client, session):
        from truthshield.infra.models import AuditLog
        email, body = signup(client)
        client.post("/api/v1/auth/signin", json={"email": email, "password": PASSWORD})
        headers = {"Authorization": f"Bearer {body['access_token']}"}
        client.post("/api/v1/investigations", json={"type": "text", "content": "audit me please"}, headers=headers)
        actions = {a.action for a in session.query(AuditLog).filter(
            AuditLog.actor_id == uuid.UUID(body["user"]["id"])).all()}
        assert {"auth.signup", "auth.signin", "investigation.create"} <= actions


class TestRateLimits:
    def test_auth_routes_carry_the_stricter_limit(self):
        """1.x defined RATE_LIMIT_AUTH and attached it to nothing."""
        from truthshield.api.limits import limiter
        from truthshield.settings import get_settings

        limited = {name.rsplit(".", 1)[-1]: [str(l.limit) for l in limits]
                   for name, limits in limiter._route_limits.items()}
        for route in ("signin", "signup", "refresh", "request_otp", "verify_otp"):
            assert route in limited, f"{route} has no route-specific limit"
        assert "analyze_text" in limited and "create" in limited
        assert get_settings().RATE_LIMIT_AUTH
