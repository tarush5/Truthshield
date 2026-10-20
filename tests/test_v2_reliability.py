"""
Investigation reliability: runs that can never finish, and duplicate submissions.
"""

import uuid
from datetime import datetime, timedelta, timezone

from truthshield.infra.models import Investigation
from truthshield.investigations import service


def _signup(client):
    email = f"rel{uuid.uuid4().hex[:10]}@example.com"
    token = client.post("/api/v1/auth/signup", json={"email": email, "password": "correct-horse-42"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return headers, client.get("/api/v1/auth/me", headers=headers).json()


def _orphan(session, user_id, *, status, minutes_ago, started=True, stage="EVIDENCE_RETRIEVAL"):
    """An investigation whose worker died: never finished, never will."""
    when = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    inv = Investigation(public_id=f"TS-2026-{uuid.uuid4().int % 10**6:06d}", user_id=uuid.UUID(user_id), type="message",
                        status=status, input_sha256=uuid.uuid4().hex * 2, excerpt="x", created_at=when,
                        started_at=when if started else None, current_stage=stage if started else None)
    session.add(inv)
    session.commit()
    return inv


class TestStaleInvestigations:
    def test_a_run_whose_worker_died_is_failed_when_viewed(self, client, session):
        headers, me = _signup(client)
        inv = _orphan(session, me["id"], status="COLLECTING_EVIDENCE", minutes_ago=30)

        body = client.get(f"/api/v1/investigations/{inv.id}", headers=headers).json()
        assert body["status"] == "FAILED"
        assert "evidence retrieval" in body["error"] and "submit it again" in body["error"]

    def test_a_run_never_picked_up_fails_after_the_queue_timeout(self, client, session):
        headers, me = _signup(client)
        waiting = _orphan(session, me["id"], status="QUEUED", minutes_ago=90, started=False)
        recent = _orphan(session, me["id"], status="QUEUED", minutes_ago=5, started=False)

        items = {i["id"]: i for i in client.get("/api/v1/investigations", headers=headers).json()["items"]}
        assert items[str(waiting.id)]["status"] == "FAILED"
        assert "never started" in items[str(waiting.id)]["error"]
        # A short wait in a busy queue is normal and is left alone.
        assert items[str(recent.id)]["status"] == "QUEUED"

    def test_a_run_in_progress_is_left_alone(self, client, session):
        headers, me = _signup(client)
        inv = _orphan(session, me["id"], status="ANALYZING", minutes_ago=2)
        assert client.get(f"/api/v1/investigations/{inv.id}", headers=headers).json()["status"] == "ANALYZING"

    def test_the_dashboard_does_not_count_dead_runs_as_in_progress(self, client, session):
        headers, me = _signup(client)
        _orphan(session, me["id"], status="PROCESSING", minutes_ago=45)
        totals = client.get("/api/v1/dashboard/summary", headers=headers).json()["totals"]
        assert totals["in_progress"] == 0 and totals["failed"] == 1

    def test_the_sweep_returns_how_many_it_marked(self, session):
        user = uuid.uuid4()
        from truthshield.infra.models import User
        session.add(User(id=user, email=f"s{uuid.uuid4().hex[:8]}@example.com", is_active=True))
        session.commit()
        _orphan(session, str(user), status="PROCESSING", minutes_ago=60)
        assert service.expire_stale(session) >= 1
        assert service.expire_stale(session) == 0  # idempotent


class TestDuplicateSubmissions:
    def test_a_double_submit_returns_the_same_investigation(self, client, session):
        headers, _ = _signup(client)
        body = {"type": "message", "content": f"Your account will be blocked, update KYC now {uuid.uuid4().hex}"}
        first = client.post("/api/v1/investigations", headers=headers, json=body)
        second = client.post("/api/v1/investigations", headers=headers, json=body)
        assert first.status_code == second.status_code == 202
        assert first.json()["id"] == second.json()["id"]
        assert second.json()["executor"] == "existing"
        assert session.query(Investigation).filter(Investigation.input_sha256 == service.hashlib.sha256(
            body["content"].encode()).hexdigest()).count() == 1

    def test_different_users_and_different_content_are_never_merged(self, client):
        a, _ = _signup(client)
        b, _ = _signup(client)
        content = f"Congratulations, you won a prize, claim now {uuid.uuid4().hex}"
        ida = client.post("/api/v1/investigations", headers=a, json={"type": "message", "content": content}).json()["id"]
        idb = client.post("/api/v1/investigations", headers=b, json={"type": "message", "content": content}).json()["id"]
        idc = client.post("/api/v1/investigations", headers=a, json={"type": "message", "content": content + " again"}).json()["id"]
        assert len({ida, idb, idc}) == 3

    def test_a_retry_after_a_failure_runs_again(self, client, session):
        headers, me = _signup(client)
        content = f"Retry me {uuid.uuid4().hex} please check this message"
        first = client.post("/api/v1/investigations", headers=headers, json={"type": "message", "content": content}).json()["id"]
        inv = session.get(Investigation, uuid.UUID(first))
        inv.status = "FAILED"
        session.commit()
        second = client.post("/api/v1/investigations", headers=headers, json={"type": "message", "content": content}).json()["id"]
        assert second != first


class TestRedelivery:
    def test_a_rerun_after_an_interrupted_attempt_leaves_one_clean_record(self, client, session):
        """Celery redelivers a task whose worker died; the rerun must not double the timeline."""
        from truthshield.infra.models import InvestigationEvent, RiskFactor
        from truthshield.investigations.pipeline import InvestigationRunner

        headers, _ = _signup(client)
        inv_id = client.post("/api/v1/investigations", headers=headers, json={"demo_id": "phishing-sms"}).json()["id"]
        inv = session.get(Investigation, uuid.UUID(inv_id))
        clean_events = session.query(InvestigationEvent).filter_by(investigation_id=inv.id).count()
        clean_factors = session.query(RiskFactor).filter_by(investigation_id=inv.id).count()
        assert clean_events == 12 and clean_factors > 0

        # Simulate the worker dying after storage but before the status flip.
        inv.status = "CALCULATING_RISK"
        session.commit()
        InvestigationRunner().run(inv.id)

        session.expire_all()
        events = session.query(InvestigationEvent).filter_by(investigation_id=inv.id).all()
        assert len(events) == 12 and sorted(e.seq for e in events) == list(range(1, 13))
        assert session.query(RiskFactor).filter_by(investigation_id=inv.id).count() == clean_factors
        assert session.get(Investigation, inv.id).status == "COMPLETED"


class TestHealthReporting:
    def test_the_broker_probe_is_cached_between_calls(self, monkeypatch):
        from truthshield.infra import celery_app as module

        calls = []

        class DeadConnection:
            def ensure_connection(self, **_):
                calls.append(1)
                raise ConnectionError("down")

            def release(self):
                pass

        monkeypatch.setattr(module.settings, "CELERY_TASK_ALWAYS_EAGER", False)
        monkeypatch.setattr(module.celery_app, "connection", lambda: DeadConnection())
        monkeypatch.setattr(module, "_probe", None)
        assert module.broker_reachable() is False
        assert module.broker_reachable() is False
        assert len(calls) == 1, "a down broker must cost one probe per window, not one per caller"
        assert module.broker_reachable(fresh=True) is False and len(calls) == 2

    def test_a_down_queue_makes_health_degraded_when_investigations_use_it(self, client, monkeypatch):
        from truthshield.infra import celery_app as module
        from truthshield.settings import get_settings

        monkeypatch.setattr(module, "broker_reachable", lambda **_: False)
        monkeypatch.setattr(get_settings(), "INVESTIGATION_EXECUTOR", "celery")
        body = client.get("/api/v1/health").json()
        assert body["status"] == "degraded" and body["broker"] is False
        assert body["broker_mode"] in ("eager", "broker")

    def test_capability_reports_do_not_import_heavy_packages(self):
        import sys

        from truthshield.detectors.base import OptionalDependency

        sys.modules.pop("this", None)
        dep = OptionalDependency("this")  # stdlib, prints on import
        assert dep.installed is True and "this" not in sys.modules
        assert OptionalDependency("definitely_not_a_module_xyz").installed is False
