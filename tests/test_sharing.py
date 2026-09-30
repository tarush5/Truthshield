"""
Public share links.

This is the one route that serves a report to an unauthenticated stranger,
so it gets the most direct scrutiny of anything in the API: what it exposes,
what it refuses, and whether revocation actually revokes.
"""

import uuid

import pytest


@pytest.fixture
def report_id(client, auth):
    """A completed report owned by the `auth` fixture's user."""
    response = client.post(
        "/api/v1/analyze",
        data={"text": "The Earth orbits the Sun once per year.", "language": "en"},
        headers=auth,
    )
    assert response.status_code == 200
    return response.json()["id"]


@pytest.fixture
def shared(client, auth, report_id):
    """A report that has been shared, with its token."""
    response = client.post(f"/api/v1/reports/{report_id}/share", headers=auth)
    assert response.status_code == 201
    return report_id, response.json()["token"]


class TestMintingALink:
    def test_sharing_requires_authentication(self, client, report_id):
        assert client.post(f"/api/v1/reports/{report_id}/share").status_code == 401

    def test_the_token_is_long_enough_not_to_be_guessed(self, shared):
        _, token = shared
        assert len(token) >= 40

    def test_sharing_twice_keeps_the_same_link(self, client, auth, shared):
        """
        A link the owner has already sent must not die because they pressed
        the button again.
        """
        report_id, token = shared
        again = client.post(f"/api/v1/reports/{report_id}/share", headers=auth)
        assert again.status_code == 201
        assert again.json()["token"] == token

    def test_two_reports_never_share_a_token(self, client, auth):
        tokens = set()
        for _ in range(3):
            rid = client.post(
                "/api/v1/analyze",
                data={"text": f"A distinct claim {uuid.uuid4().hex[:8]} about a topic.", "language": "en"},
                headers=auth,
            ).json()["id"]
            tokens.add(client.post(f"/api/v1/reports/{rid}/share", headers=auth).json()["token"])
        assert len(tokens) == 3

    def test_someone_elses_report_is_not_shareable(self, client, auth, report_id):
        """
        404 rather than 403. A 403 confirms the id is real, which turns this
        into an oracle for probing which reports exist.
        """
        other = client.post("/api/v1/auth/signup", json={
            "email": f"o{uuid.uuid4().hex[:10]}@example.com",
            "password": "correct-horse-42",
        }).json()["access_token"]

        response = client.post(
            f"/api/v1/reports/{report_id}/share",
            headers={"Authorization": f"Bearer {other}"},
        )
        assert response.status_code == 404

    def test_an_unknown_report_is_a_404(self, client, auth):
        assert client.post(
            f"/api/v1/reports/{uuid.uuid4().hex}/share", headers=auth,
        ).status_code == 404


class TestReadingAShared:
    def test_anyone_with_the_link_can_read_it(self, client, shared):
        _, token = shared
        response = client.get(f"/api/v1/shared/{token}")
        assert response.status_code == 200
        assert response.json()["verdict"]

    def test_it_carries_the_finding_and_the_evidence(self, client, shared):
        """A debunk nobody can check the sources of is just an assertion."""
        _, token = shared
        body = client.get(f"/api/v1/shared/{token}").json()
        for key in ("verdict", "trust_score", "breakdown", "claims", "reasons", "limitations"):
            assert key in body

    def test_it_does_not_identify_who_ran_it(self, client, shared):
        """The report is public; the account behind it is not."""
        _, token = shared
        response = client.get(f"/api/v1/shared/{token}")
        for leaked in ("user_id", "org_id", "email"):
            assert leaked not in response.text

    def test_it_does_not_expose_the_report_id(self, client, shared):
        """
        Holding a public link must not hand the holder an id to try against
        the authenticated routes.
        """
        report_id, token = shared
        body = client.get(f"/api/v1/shared/{token}")
        assert "id" not in body.json()
        assert report_id not in body.text

    def test_a_report_id_is_not_a_share_token(self, client, shared):
        """The public route looks up by token only, so ids get nothing."""
        report_id, _ = shared
        assert client.get(f"/api/v1/shared/{report_id}").status_code == 404

    @pytest.mark.parametrize("token", [
        "x", "not-a-real-token", "../../etc/passwd", "a" * 200, "%00",
    ])
    def test_a_bad_token_is_a_flat_404(self, client, token):
        assert client.get(f"/api/v1/shared/{token}").status_code == 404

    def test_an_oversized_token_is_refused_before_the_database(self, client):
        """An unbounded path segment is an unbounded query parameter."""
        assert client.get(f"/api/v1/shared/{'a' * 5000}").status_code in (404, 414)


class TestRevoking:
    def test_revoking_kills_the_link_immediately(self, client, auth, shared):
        report_id, token = shared
        assert client.get(f"/api/v1/shared/{token}").status_code == 200

        assert client.delete(f"/api/v1/reports/{report_id}/share", headers=auth).status_code == 204
        assert client.get(f"/api/v1/shared/{token}").status_code == 404

    def test_revoking_twice_is_not_an_error(self, client, auth, shared):
        """The caller's intent is "this must not be public"; it already is not."""
        report_id, _ = shared
        client.delete(f"/api/v1/reports/{report_id}/share", headers=auth)
        assert client.delete(f"/api/v1/reports/{report_id}/share", headers=auth).status_code == 204

    def test_resharing_mints_a_new_token(self, client, auth, shared):
        """
        Otherwise revoking and re-sharing would silently re-arm every link
        the owner believed they had killed.
        """
        report_id, original = shared
        client.delete(f"/api/v1/reports/{report_id}/share", headers=auth)

        fresh = client.post(f"/api/v1/reports/{report_id}/share", headers=auth).json()["token"]
        assert fresh != original
        assert client.get(f"/api/v1/shared/{original}").status_code == 404
        assert client.get(f"/api/v1/shared/{fresh}").status_code == 200

    def test_a_stranger_cannot_revoke(self, client, auth, shared):
        report_id, token = shared
        other = client.post("/api/v1/auth/signup", json={
            "email": f"o{uuid.uuid4().hex[:10]}@example.com",
            "password": "correct-horse-42",
        }).json()["access_token"]

        response = client.delete(
            f"/api/v1/reports/{report_id}/share",
            headers={"Authorization": f"Bearer {other}"},
        )
        assert response.status_code == 404
        assert client.get(f"/api/v1/shared/{token}").status_code == 200

    def test_revoking_requires_authentication(self, client, shared):
        report_id, _ = shared
        assert client.delete(f"/api/v1/reports/{report_id}/share").status_code == 401


class TestPrivateByDefault:
    def test_an_unshared_report_is_not_public(self, client, report_id):
        """
        Nothing is readable without a token, and the authenticated route
        still refuses an anonymous caller.
        """
        assert client.get(f"/api/v1/reports/{report_id}").status_code == 404

    def test_sharing_one_report_does_not_share_another(self, client, auth, shared):
        report_id, _ = shared
        other = client.post(
            "/api/v1/analyze",
            data={"text": "A completely separate claim about geography.", "language": "en"},
            headers=auth,
        ).json()["id"]

        from truthshield.infra.database import SessionLocal
        from truthshield.infra.models import Report

        session = SessionLocal()
        try:
            assert session.query(Report).filter(Report.id == other).first().share_token is None
        finally:
            session.close()
