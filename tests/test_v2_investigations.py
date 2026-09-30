"""
Investigations through the real app: intake, pipeline, timeline, access
control, listing, export, deletion, dashboard aggregates.
"""

import csv
import io
import uuid

import pytest

SPEC_EXAMPLE = ("Congratulations! You have won ₹50,000. Click this link to claim your reward: "
                "http://reward-claim-sbi.top/verify")

ALL_STAGES = [
    "VALIDATION", "HASHING", "EXTRACTION", "CLASSIFICATION", "FEATURE_EXTRACTION",
    "MODEL_ANALYSIS", "EVIDENCE_RETRIEVAL", "CROSS_MODAL_ANALYSIS", "RISK_ENGINE",
    "EXPLANATION", "REPORT", "STORAGE",
]


def create(client, auth, **body):
    r = client.post("/api/v1/investigations", json=body, headers=auth)
    assert r.status_code == 202, r.text
    return r.json()


def fetch(client, auth, ident):
    r = client.get(f"/api/v1/investigations/{ident}", headers=auth)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def other_auth(client):
    email = f"o{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/api/v1/auth/signup", json={"email": email, "password": "correct-horse-42"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class TestLifecycle:
    def test_spec_example_end_to_end(self, client, auth):
        created = create(client, auth, type="message", content=SPEC_EXAMPLE)
        assert created["public_id"].startswith("TS-") and len(created["public_id"]) == 14

        inv = fetch(client, auth, created["id"])
        assert inv["status"] == "COMPLETED"
        result = inv["result"]

        # Score, level and a confidence that is its own axis.
        assert inv["risk_score"] >= 65 and inv["risk_level"] in ("HIGH", "CRITICAL")
        assert 0 < inv["confidence"] <= 0.85
        assert result["risk"]["represents"]

        # The breakdown is visible and adds up.
        contributions = result["risk"]["contributions"]
        assert sum(c["points"] for c in contributions) == inv["risk_score"]
        assert all(c["provenance"] and c["engine"] for c in contributions)

        # Uncertainty is explicit, including what offline mode skipped.
        assert any("reputation" in u for u in result["uncertainties"])
        assert result["recommended_actions"]["do_not"]
        assert result["explanation"]["llm"] is None

    def test_every_stage_is_recorded_in_order(self, client, auth):
        inv = fetch(client, auth, create(client, auth, type="message", content=SPEC_EXAMPLE)["id"])
        assert [e["stage"] for e in inv["timeline"]] == ALL_STAGES
        assert all(e["status"] in ("completed", "skipped") for e in inv["timeline"])
        assert all(e["duration_ms"] is not None and e["service"] for e in inv["timeline"])
        skipped = {e["stage"]: e["message"] for e in inv["timeline"] if e["status"] == "skipped"}
        assert "EVIDENCE_RETRIEVAL" in skipped and skipped["EVIDENCE_RETRIEVAL"]

    def test_input_is_hashed_and_preserved(self, client, auth):
        import hashlib
        inv = fetch(client, auth, create(client, auth, type="text", content=SPEC_EXAMPLE)["id"])
        assert inv["input"]["content"] == SPEC_EXAMPLE
        assert inv["input"]["sha256"] == hashlib.sha256(SPEC_EXAMPLE.encode()).hexdigest()
        assert inv["input_sha256"] == inv["input"]["sha256"]

    def test_predictions_are_versioned_and_keyed_by_input(self, client, auth):
        inv = fetch(client, auth, create(client, auth, type="message", content=SPEC_EXAMPLE)["id"])
        assert inv["model_predictions"]
        for p in inv["model_predictions"]:
            assert p["model_name"] and p["model_version"] and p["model_kind"] and p["input_sha256"]

    def test_url_investigation(self, client, auth):
        inv = fetch(client, auth, create(client, auth, type="url", content="paypa1-secure.click/signin")["id"])
        assert inv["status"] == "COMPLETED"
        intel = inv["result"]["url_intelligence"][0]
        assert intel["url"].startswith("http://") and "entropy" in intel["features"]
        assert "typosquat_domain" in {c["code"] for c in inv["result"]["risk"]["contributions"]}
        stages = {e["stage"]: e["status"] for e in inv["timeline"]}
        assert stages["EXTRACTION"] == "skipped"

    def test_public_ids_are_sequential(self, client, auth):
        a = create(client, auth, type="text", content="first message here")["public_id"]
        b = create(client, auth, type="text", content="second message here")["public_id"]
        assert int(b.rsplit("-", 1)[1]) == int(a.rsplit("-", 1)[1]) + 1

    def test_timestamps_carry_an_explicit_utc_offset(self, client, auth):
        """Naive timestamps are read as local time by browsers ("6h ago" in IST)."""
        inv = fetch(client, auth, create(client, auth, type="text", content="timezone check")["id"])
        for value in [inv["created_at"], inv["completed_at"]] + [e["started_at"] for e in inv["timeline"]]:
            assert value.endswith("+00:00"), value

    def test_lookup_by_public_id(self, client, auth):
        created = create(client, auth, type="text", content="lookup by public id")
        assert fetch(client, auth, created["public_id"])["id"] == created["id"]


class TestDemo:
    def test_catalogue_is_public_and_lists_planned_modalities(self, client):
        body = client.get("/api/v1/demo/samples").json()
        assert {s["id"] for s in body["samples"]} >= {"prize-scam", "suspicious-url", "benign-message"}
        assert all("phase" in p for p in body["planned"])

    def test_demo_runs_the_real_pipeline_and_is_flagged(self, client, auth):
        inv = fetch(client, auth, create(client, auth, demo_id="phishing-sms")["id"])
        assert inv["is_demo"] and inv["status"] == "COMPLETED"
        assert len(inv["timeline"]) == len(ALL_STAGES)

    def test_benign_sample_is_low_risk_with_low_confidence(self, client, auth):
        inv = fetch(client, auth, create(client, auth, demo_id="benign-message")["id"])
        assert inv["risk_level"] == "LOW" and inv["classification"] == "no_significant_signals"
        assert inv["confidence_band"] in ("LOW", "VERY_LOW")

    def test_unknown_demo(self, client, auth):
        r = client.post("/api/v1/investigations", json={"demo_id": "nope"}, headers=auth)
        assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


class TestValidation:
    @pytest.mark.parametrize("body,status,code", [
        ({"type": "text", "content": "   "}, 400, "BAD_REQUEST"),
        ({"type": "url", "content": "ftp://files.example.com/x"}, 400, "UNSUPPORTED_INPUT"),
        ({"type": "url", "content": "not a url at all"}, 400, "UNSUPPORTED_INPUT"),
        ({"type": "video", "content": "x"}, 422, "VALIDATION_ERROR"),
    ])
    def test_rejections_use_the_error_envelope(self, client, auth, body, status, code):
        r = client.post("/api/v1/investigations", json=body, headers=auth)
        assert r.status_code == status
        error = r.json()["error"]
        assert error["code"] == code and error["message"] and error["request_id"]
        assert "detail" in r.json(), "1.x clients read detail"

    def test_oversized_content(self, client, auth):
        from truthshield.settings import get_settings
        big = "a " * (get_settings().MAX_TEXT_LENGTH // 2 + 10)
        r = client.post("/api/v1/investigations", json={"type": "text", "content": big}, headers=auth)
        assert r.status_code == 413 and r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"

    def test_requires_authentication(self, client):
        r = client.post("/api/v1/investigations", json={"type": "text", "content": "x"})
        assert r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHENTICATED"


class TestAccess:
    def test_another_user_gets_404_not_403(self, client, auth, other_auth):
        created = create(client, auth, type="text", content="private investigation")
        for path in ("", "/events", "/export"):
            r = client.get(f"/api/v1/investigations/{created['id']}{path}", headers=other_auth)
            assert r.status_code == 404
        assert client.delete(f"/api/v1/investigations/{created['id']}", headers=other_auth).status_code == 404

    def test_lists_are_scoped_to_the_owner(self, client, auth, other_auth):
        created = create(client, auth, type="text", content="scoped listing check")
        mine = client.get("/api/v1/investigations?page_size=100", headers=auth).json()
        theirs = client.get("/api/v1/investigations?page_size=100", headers=other_auth).json()
        assert created["id"] in {i["id"] for i in mine["items"]}
        assert created["id"] not in {i["id"] for i in theirs["items"]}


class TestHistory:
    def test_search_filter_sort_paginate(self, client, other_auth):
        a = other_auth
        create(client, a, type="text", content="Hello there, a normal note about lunch plans tomorrow.")
        risky = create(client, a, demo_id="prize-scam")
        create(client, a, type="url", content="https://example.org/about")

        page = client.get("/api/v1/investigations?page=1&page_size=2", headers=a).json()
        assert page["total"] == 3 and len(page["items"]) == 2

        top = client.get("/api/v1/investigations?sort=-risk_score", headers=a).json()["items"][0]
        assert top["id"] == risky["id"]

        by_type = client.get("/api/v1/investigations?type=url", headers=a).json()
        assert by_type["total"] == 1

        found = client.get(f"/api/v1/investigations?q={risky['public_id']}", headers=a).json()
        assert [i["id"] for i in found["items"]] == [risky["id"]]

        high = client.get("/api/v1/investigations?risk_level=CRITICAL", headers=a).json()
        assert all(i["risk_level"] == "CRITICAL" for i in high["items"])

    def test_excerpts_are_redacted(self, client, auth):
        created = create(client, auth, type="message",
                         content="Your OTP is 482913. Card 4111 1111 1111 1111 will be blocked, call now.")
        item = fetch(client, auth, created["id"])
        assert "4111 1111 1111 1111" not in item["excerpt"]
        assert "4111 1111 1111 1111" in item["input"]["content"], "the owner still sees the original"

    def test_delete_removes_everything(self, client, auth, session):
        from truthshield.infra.models import InvestigationEvent, InvestigationInput, RiskFactor
        created = create(client, auth, demo_id="prize-scam")
        assert client.delete(f"/api/v1/investigations/{created['id']}", headers=auth).status_code == 204
        assert client.get(f"/api/v1/investigations/{created['id']}", headers=auth).status_code == 404
        inv_id = uuid.UUID(created["id"])
        for model in (InvestigationEvent, InvestigationInput, RiskFactor):
            assert session.query(model).filter(model.investigation_id == inv_id).count() == 0


class TestExport:
    def test_json_export_omits_the_original_input(self, client, auth):
        created = create(client, auth, type="message", content="Card 4111 1111 1111 1111 blocked, verify now")
        r = client.get(f"/api/v1/investigations/{created['id']}/export?format=json", headers=auth)
        assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
        body = r.json()
        assert body["input"]["content"] is None and body["result"]

    def test_csv_export_neutralises_formulas(self, client, auth, session):
        from truthshield.infra.models import RiskFactor
        created = create(client, auth, demo_id="prize-scam")
        factor = session.query(RiskFactor).filter(RiskFactor.investigation_id == uuid.UUID(created["id"])).first()
        factor.evidence = "=HYPERLINK(\"http://evil\")"
        session.commit()
        r = client.get(f"/api/v1/investigations/{created['id']}/export?format=csv", headers=auth)
        rows = list(csv.reader(io.StringIO(r.text)))
        assert rows[0][0] == "investigation"
        assert all(not cell.startswith("=") for row in rows for cell in row)


class TestSynchronousAnalysis:
    def test_analyze_text_returns_a_completed_investigation(self, client, auth):
        r = client.post("/api/v1/analyze/text", json={"content": SPEC_EXAMPLE}, headers=auth)
        assert r.status_code == 200 and r.json()["status"] == "COMPLETED"

    def test_analyze_url(self, client, auth):
        r = client.post("/api/v1/analyze/url", json={"url": "http://sbi-kyc-update.top/login"}, headers=auth)
        assert r.status_code == 200 and r.json()["risk_score"] > 0

    def test_analyze_email(self, client, auth):
        email = ("From: \"PayPal Support\" <help@paypa1-support.xyz>\nReply-To: agent@gmail.com\n"
                 "Subject: Account suspended\n\nVerify your account within 24 hours.")
        r = client.post("/api/v1/analyze/email", json={"content": email}, headers=auth)
        codes = {c["code"] for c in r.json()["result"]["risk"]["contributions"]}
        assert "replyto_mismatch" in codes or "display_name_mismatch" in codes


class TestExecutors:
    def test_celery_executor_runs_the_registered_task(self, client, auth, monkeypatch):
        """The docker-compose stack dispatches to the worker; the task must be wired."""
        from truthshield.infra import celery_app
        from truthshield.settings import get_settings

        monkeypatch.setattr(get_settings(), "INVESTIGATION_EXECUTOR", "celery")
        monkeypatch.setattr(celery_app, "broker_reachable", lambda: True)
        created = create(client, auth, type="message", content=SPEC_EXAMPLE)   # eager in tests
        assert created["executor"] == "celery"
        assert fetch(client, auth, created["id"])["status"] == "COMPLETED"

    def test_celery_executor_refuses_when_the_broker_is_down(self, client, auth, monkeypatch):
        from truthshield.infra import celery_app
        from truthshield.settings import get_settings

        monkeypatch.setattr(get_settings(), "INVESTIGATION_EXECUTOR", "celery")
        monkeypatch.setattr(celery_app, "broker_reachable", lambda: False)
        r = client.post("/api/v1/investigations", json={"type": "text", "content": "queued?"}, headers=auth)
        assert r.status_code == 503 and r.json()["error"]["code"] == "UNAVAILABLE"

        latest = client.get("/api/v1/investigations?q=queued", headers=auth).json()["items"][0]
        assert latest["status"] == "FAILED", "no orphaned QUEUED record"


class TestFailure:
    def test_an_engine_crash_is_reported_not_hidden(self, client, auth, monkeypatch):
        from truthshield.investigations.engines.text import TextEngine

        def boom(self, ctx, result):
            raise RuntimeError("model exploded")

        monkeypatch.setattr(TextEngine, "_run", boom)
        inv = fetch(client, auth, create(client, auth, type="message", content=SPEC_EXAMPLE)["id"])
        assert inv["status"] == "COMPLETED"
        text = next(e for e in inv["result"]["engines"] if e["name"] == "text")
        assert text["status"] == "error"
        assert any("text engine failed" in u for u in inv["result"]["uncertainties"])
        assert "model exploded" not in str(inv), "internal error text never reaches the client"

    def test_a_pipeline_failure_marks_the_investigation_failed(self, client, auth, monkeypatch):
        from truthshield.investigations import risk

        def boom(self, *a, **k):
            raise RuntimeError("scoring broke")

        monkeypatch.setattr(risk.RiskEngine, "assess", boom)
        inv = fetch(client, auth, create(client, auth, type="text", content="anything at all here")["id"])
        assert inv["status"] == "FAILED" and inv["error"] and "scoring broke" not in inv["error"]
        assert inv["timeline"][-1]["stage"] == "RISK_ENGINE" and inv["timeline"][-1]["status"] == "failed"


class TestDashboard:
    def test_aggregates_reflect_stored_investigations(self, client):
        email = f"d{uuid.uuid4().hex[:10]}@example.com"
        token = client.post("/api/v1/auth/signup", json={"email": email, "password": "correct-horse-42"}).json()["access_token"]
        a = {"Authorization": f"Bearer {token}"}

        empty = client.get("/api/v1/dashboard/summary", headers=a).json()
        assert empty["totals"]["investigations"] == 0 and empty["average_risk"] is None

        create(client, a, demo_id="prize-scam")
        create(client, a, demo_id="benign-message")
        body = client.get("/api/v1/dashboard/summary?days=7", headers=a).json()
        assert body["totals"]["investigations"] == 2 and body["totals"]["completed"] == 2
        assert sum(body["risk_levels"].values()) == 2
        assert len(body["volume"]) == 7 and body["volume"][-1]["total"] == 2
        assert body["latency_ms"]["samples"] == 2 and body["latency_ms"]["p50"] is not None
        assert body["top_risk_factors"] and len(body["recent"]) == 2


class TestPlatform:
    def test_system_health_reports_capabilities_honestly(self, client):
        body = client.get("/api/v1/system/health").json()
        assert {e["name"] for e in body["engines"]} == {"text", "url", "evidence"}
        assert body["investigations"]["offline_mode"] is True
        assert body["investigations"]["evidence_retrieval"] is False

    def test_engines_expose_the_active_risk_config(self, client, auth):
        body = client.get("/api/v1/engines", headers=auth).json()
        assert body["risk"]["weights"]["url"] == 20 and body["risk"]["version"]
