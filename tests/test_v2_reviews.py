"""
Human review, appeals, reanalysis and review-based accuracy -- through the real app.
"""

import uuid

import pytest

PASSWORD = "correct-horse-42"
SCAM = ("Congratulations! You have won Rs 50,000. Click this link to claim your reward: "
        "http://reward-claim-sbi.top/verify")
BENIGN = "Team lunch moved to 1:30 on Thursday, same place as last time."


def account(client, role=None):
    email = f"r{uuid.uuid4().hex[:10]}@example.com"
    body = client.post("/api/v1/auth/signup", json={"email": email, "password": PASSWORD}).json()
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    if role:
        from truthshield.infra.database import SessionLocal
        from truthshield.infra.models import User
        s = SessionLocal()
        s.get(User, uuid.UUID(body["user"]["id"])).role = role
        s.commit()
        s.close()
    return headers


@pytest.fixture
def user(client):
    return account(client)


@pytest.fixture
def analyst(client):
    return account(client, role="ANALYST")


def investigate(client, headers, content, unique=True):
    if unique:
        content = f"{content} [{uuid.uuid4().hex[:6]}]"
    r = client.post("/api/v1/investigations", json={"type": "message", "content": content}, headers=headers)
    assert r.status_code == 202, r.text
    inv = client.get(f"/api/v1/investigations/{r.json()['id']}", headers=headers).json()
    assert inv["status"] == "COMPLETED"
    return inv


def feedback(client, headers, ident, **body):
    return client.post(f"/api/v1/investigations/{ident}/feedback", json=body, headers=headers)


class TestFeedbackAndAppeals:
    def test_feedback_is_recorded_beside_the_result_and_never_changes_it(self, client, user):
        inv = investigate(client, user, SCAM)
        r = feedback(client, user, inv["id"], label="legitimate",
                     comment="My card 4111 1111 1111 1111 was fine")
        assert r.status_code == 201, r.text
        review = r.json()
        assert review["status"] == "recorded" and review["kind"] == "feedback"
        assert "4111 1111 1111 1111" not in review["comment"], "comments are redacted before storage"
        assert review["system"]["level"] == inv["risk_level"]
        assert review["system"]["config_version"]

        after = client.get(f"/api/v1/investigations/{inv['id']}", headers=user).json()
        assert (after["risk_score"], after["risk_level"]) == (inv["risk_score"], inv["risk_level"])
        assert after["review"]["count"] == 1

    def test_second_feedback_replaces_the_first(self, client, user):
        inv = investigate(client, user, SCAM)
        feedback(client, user, inv["id"], label="unsure")
        feedback(client, user, inv["id"], label="fraud")
        items = client.get(f"/api/v1/investigations/{inv['id']}/reviews", headers=user).json()["items"]
        assert [i["user_label"] for i in items] == ["fraud"]

    def test_one_open_appeal_at_a_time(self, client, user):
        inv = investigate(client, user, SCAM)
        assert feedback(client, user, inv["id"], label="legitimate", appeal=True).json()["status"] == "open"
        r = feedback(client, user, inv["id"], label="legitimate", appeal=True)
        assert r.status_code == 409 and r.json()["error"]["code"] == "APPEAL_OPEN"

    def test_bad_label_is_rejected(self, client, user):
        inv = investigate(client, user, SCAM)
        assert feedback(client, user, inv["id"], label="maybe").status_code == 422

    def test_another_users_investigation_is_not_found(self, client, user):
        inv = investigate(client, user, SCAM)
        stranger = account(client)
        assert feedback(client, stranger, inv["id"], label="fraud").status_code == 404
        assert client.get(f"/api/v1/investigations/{inv['id']}/reviews", headers=stranger).status_code == 404


class TestReviewerWorkflow:
    def test_users_cannot_reach_the_queue(self, client, user):
        assert client.get("/api/v1/admin/reviews", headers=user).status_code == 403
        assert client.get("/api/v1/admin/reviews/accuracy", headers=user).status_code == 403

    def test_appeal_reaches_the_queue_and_is_resolved(self, client, user, analyst):
        inv = investigate(client, user, SCAM)
        appeal = feedback(client, user, inv["id"], label="legitimate", appeal=True,
                          comment="call me on 9876543210").json()

        queue = client.get("/api/v1/admin/reviews?kind=appeal", headers=analyst).json()
        assert appeal["id"] in {i["id"] for i in queue["items"]}

        detail = client.get(f"/api/v1/admin/reviews/{appeal['id']}", headers=analyst).json()
        assert detail["investigation"]["public_id"] == inv["public_id"]
        assert "content" not in detail["investigation"], "reviewers see the redacted input only"
        assert "9876543210" not in (detail["comment"] or "")

        r = client.patch(f"/api/v1/admin/reviews/{appeal['id']}", headers=analyst,
                         json={"label": "fraud", "note": "Lookalike domain; result stands."})
        assert r.status_code == 200 and r.json()["status"] == "resolved"

        after = client.get(f"/api/v1/investigations/{inv['id']}", headers=user).json()
        assert after["review"] == {"count": 1, "open_appeal": False, "reviewer_label": "fraud",
                                   "reviewed_at": after["review"]["reviewed_at"]}
        assert after["risk_score"] == inv["risk_score"], "a reviewer decision never rewrites the result"

        # The queue of open items no longer has it.
        queue = client.get("/api/v1/admin/reviews?kind=appeal", headers=analyst).json()
        assert appeal["id"] not in {i["id"] for i in queue["items"]}

    def test_a_reviewer_cannot_decide_their_own_appeal(self, client, analyst):
        inv = investigate(client, analyst, SCAM)
        appeal = feedback(client, analyst, inv["id"], label="legitimate", appeal=True).json()
        r = client.patch(f"/api/v1/admin/reviews/{appeal['id']}", headers=analyst, json={"label": "fraud"})
        assert r.status_code == 403

    def test_unknown_review_is_404(self, client, analyst):
        assert client.get(f"/api/v1/admin/reviews/{uuid.uuid4()}", headers=analyst).status_code == 404
        assert client.get("/api/v1/admin/reviews/not-a-uuid", headers=analyst).status_code == 404


class TestReviewAccuracy:
    def test_confusion_counts_follow_reviewer_decisions(self, client, user, analyst):
        before = client.get("/api/v1/admin/reviews/accuracy", headers=analyst).json()["confusion"]

        scam = investigate(client, user, SCAM)
        benign = investigate(client, user, BENIGN)
        assert scam["risk_level"] in ("MEDIUM", "HIGH", "CRITICAL")
        assert benign["risk_level"] == "LOW"

        decisions = [(scam, "fraud"), (benign, "fraud")]   # one true positive, one false negative
        for inv, label in decisions:
            review = feedback(client, user, inv["id"], label="unsure", appeal=True).json()
            client.patch(f"/api/v1/admin/reviews/{review['id']}", headers=analyst, json={"label": label})

        report = client.get("/api/v1/admin/reviews/accuracy", headers=analyst).json()
        after = report["confusion"]
        assert after["true_positive"] - before["true_positive"] == 1
        assert after["false_negative"] - before["false_negative"] == 1
        assert report["caveats"] and report["flagged_means"]
        assert report["submitter_feedback"]["note"]


class TestReanalysis:
    def test_reanalysis_creates_a_linked_run_and_keeps_the_original(self, client, user):
        inv = investigate(client, user, SCAM)
        r = client.post(f"/api/v1/investigations/{inv['id']}/reanalyze", headers=user)
        assert r.status_code == 202, r.text
        new_id = r.json()["id"]
        assert new_id != inv["id"], "re-running bypasses the duplicate guard"

        new = client.get(f"/api/v1/investigations/{new_id}", headers=user).json()
        assert new["status"] == "COMPLETED"
        assert new["input_sha256"] == inv["input_sha256"]
        prev = new["reanalysis_of"]
        assert prev["public_id"] == inv["public_id"] and prev["available"]
        assert prev["risk_score"] == inv["risk_score"] and prev["config_version"]

        original = client.get(f"/api/v1/investigations/{inv['id']}", headers=user).json()
        assert original["reanalysis_of"] is None
        assert original["result"] == inv["result"]

    def test_link_survives_deletion_of_the_original(self, client, user):
        inv = investigate(client, user, SCAM)
        new_id = client.post(f"/api/v1/investigations/{inv['id']}/reanalyze", headers=user).json()["id"]
        assert client.delete(f"/api/v1/investigations/{inv['id']}", headers=user).status_code == 204
        prev = client.get(f"/api/v1/investigations/{new_id}", headers=user).json()["reanalysis_of"]
        assert prev == {"public_id": inv["public_id"], "available": False}

    def test_cannot_reanalyze_someone_elses(self, client, user):
        inv = investigate(client, user, SCAM)
        assert client.post(f"/api/v1/investigations/{inv['id']}/reanalyze",
                           headers=account(client)).status_code == 404


class TestReviewPrivacyAndCategories:
    def test_plain_feedback_never_exposes_content_to_reviewers(self, client, user, analyst):
        inv = investigate(client, user, SCAM)
        fb = feedback(client, user, inv["id"], label="legitimate", category="false_positive").json()
        detail = client.get(f"/api/v1/admin/reviews/{fb['id']}", headers=analyst).json()
        assert detail["investigation"]["content_available"] is False
        assert "redacted_input" not in detail["investigation"] and "result" not in detail["investigation"]
        assert detail["category"] == "false_positive"

    def test_feedback_can_name_a_finding_from_this_result_only(self, client, user):
        inv = investigate(client, user, SCAM)
        code = inv["risk_factors"][0]["code"]
        r = feedback(client, user, inv["id"], label="legitimate", category="false_positive", finding=code)
        assert r.status_code == 201 and r.json()["finding"] == code
        bad = feedback(client, user, inv["id"], label="legitimate", finding="not_a_real_signal")
        assert bad.status_code == 400

    def test_detector_versions_are_snapshotted(self, client, user):
        inv = investigate(client, user, SCAM)
        versions = feedback(client, user, inv["id"], label="fraud").json()["system"]["versions"]
        assert versions["text"] and versions["schema"] == inv["result"]["schema_version"]

    def test_unknown_category_is_rejected(self, client, user):
        inv = investigate(client, user, SCAM)
        assert feedback(client, user, inv["id"], label="fraud", category="vibes").status_code == 422


class TestReanalysisChanges:
    def test_identical_rerun_reports_no_difference(self, client, user):
        inv = investigate(client, user, SCAM)
        new_id = client.post(f"/api/v1/investigations/{inv['id']}/reanalyze", headers=user).json()["id"]
        changes = client.get(f"/api/v1/investigations/{new_id}", headers=user).json()["reanalysis_of"]["changes"]
        assert changes["unchanged"] is True
        assert changes["reasons"] == ["No difference: the same input produced the same result."]

    def test_differences_are_named(self):
        from truthshield.investigations.service import result_changes

        before = {"classification": "potential_scam", "engines": [{"name": "text", "version": "1.0"}],
                  "risk": {"score": 40, "level": "MEDIUM", "config": {"version": "a"},
                           "contributions": [{"code": "old_sig", "title": "Old", "points": 40}]},
                  "claims": [{"text": "The bridge reopened.", "assessment": "INSUFFICIENT_EVIDENCE"}]}
        after = {"classification": "potential_scam", "engines": [{"name": "text", "version": "1.1"}],
                 "risk": {"score": 70, "level": "HIGH", "config": {"version": "a"},
                          "contributions": [{"code": "new_sig", "title": "New", "points": 70}]},
                 "claims": [{"text": "The bridge reopened.", "assessment": "SUPPORTED"}]}
        c = result_changes(before, after)
        assert c["score"] == {"before": 40, "after": 70} and c["level"]["after"] == "HIGH"
        assert c["signals_added"] == [{"code": "new_sig", "title": "New"}]
        assert c["signals_removed"] == [{"code": "old_sig", "title": "Old"}]
        assert c["engines_changed"] == [{"engine": "text", "before": "1.0", "after": "1.1"}]
        assert c["claims_changed"][0]["after"] == "SUPPORTED"
        assert not c["config_changed"] and not c["unchanged"]
        assert any("text 1.0 -> 1.1" in r for r in c["reasons"])
