"""
Account deletion (DELETE /api/v1/auth/me).

A deleted account must take its data with it: investigations, their stored
files, 1.x reports, the personal workspace and every session. Unowned 1.x
reports are readable by anyone with the id, so leaving them behind would
publish them.
"""

import uuid

from truthshield.infra.models import Investigation, OrganizationMember, Report, User

PASSWORD = "correct-horse-42"


def signup(client):
    email = f"del{uuid.uuid4().hex[:10]}@example.com"
    tokens = client.post("/api/v1/auth/signup", json={"email": email, "password": PASSWORD}).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=headers).json()
    return email, headers, tokens["refresh_token"], me


def delete(client, headers, **body):
    return client.request("DELETE", "/api/v1/auth/me", headers=headers, json=body)


def test_deleting_an_account_removes_everything_it_owns(client, session):
    email, headers, refresh, me = signup(client)
    inv_id = client.post("/api/v1/investigations", headers=headers, json={"demo_id": "phishing-sms"}).json()["id"]
    report_id = uuid.uuid4().hex
    session.add(Report(id=report_id, user_id=uuid.UUID(me["id"]), org_id=uuid.UUID(me["org_id"]), status="complete",
                       input_text="a private 1.x submission", verdict="UNVERIFIED", trust_score=50, content_type="text"))
    session.commit()

    assert delete(client, headers, confirm_email=email, password=PASSWORD).status_code == 204

    session.expire_all()
    assert session.get(User, uuid.UUID(me["id"])) is None
    assert session.get(Investigation, uuid.UUID(inv_id)) is None
    assert session.get(Report, report_id) is None
    # The report is gone rather than orphaned (an orphan would be public).
    assert client.get(f"/api/v1/reports/{report_id}").status_code == 404
    # Every session ends.
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": refresh}).status_code == 401
    assert client.post("/api/v1/auth/signin", json={"email": email, "password": PASSWORD}).status_code == 401


def test_confirmation_and_password_are_required(client, session):
    email, headers, _, me = signup(client)
    assert delete(client, headers, confirm_email="someone-else@example.com", password=PASSWORD).status_code == 400
    # 403, not 401: a wrong confirmation must not read as an expired session.
    assert delete(client, headers, confirm_email=email, password="wrong-password-1").status_code == 403
    assert delete(client, headers, confirm_email=email).status_code == 403
    session.expire_all()
    assert session.get(User, uuid.UUID(me["id"])) is not None


def test_other_users_are_untouched(client, session):
    email, headers, _, _ = signup(client)
    _, other_headers, _, other = signup(client)
    other_inv = client.post("/api/v1/investigations", headers=other_headers, json={"demo_id": "benign-message"}).json()["id"]

    assert delete(client, headers, confirm_email=email, password=PASSWORD).status_code == 204
    session.expire_all()
    assert session.get(User, uuid.UUID(other["id"])) is not None
    assert client.get(f"/api/v1/investigations/{other_inv}", headers=other_headers).status_code == 200


def test_a_workspace_shared_with_others_blocks_deletion(client, session):
    email, headers, _, me = signup(client)
    _, _, _, other = signup(client)
    session.add(OrganizationMember(org_id=uuid.UUID(me["org_id"]), user_id=uuid.UUID(other["id"]), role="Member"))
    session.commit()

    response = delete(client, headers, confirm_email=email, password=PASSWORD)
    assert response.status_code == 409
    session.expire_all()
    assert session.get(User, uuid.UUID(me["id"])) is not None


def test_unauthenticated_requests_are_refused(client):
    assert client.request("DELETE", "/api/v1/auth/me", json={"confirm_email": "a@example.com"}).status_code == 401
