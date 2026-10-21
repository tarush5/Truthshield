"""Evidence retrieval overlaps the URL engine's network wait."""

import threading
import time

from truthshield.investigations.engines.evidence import EvidenceEngine
from truthshield.investigations.engines.url import UrlEngine

TEXT = "The city council confirmed the bridge reopened on Monday. Details: http://news-example.org/bridge"


def test_evidence_runs_while_the_url_engine_waits(client, auth, monkeypatch):
    evidence_started = threading.Event()
    overlapped = []
    orig_url, orig_ev = UrlEngine._run, EvidenceEngine._run

    def url_run(self, ctx, result):
        # Sequential execution would never set the event while we wait here.
        overlapped.append(evidence_started.wait(timeout=5))
        return orig_url(self, ctx, result)

    def ev_run(self, ctx, result):
        evidence_started.set()
        return orig_ev(self, ctx, result)

    monkeypatch.setattr(UrlEngine, "_run", url_run)
    monkeypatch.setattr(EvidenceEngine, "_run", ev_run)
    r = client.post("/api/v1/investigations", json={"type": "text", "content": TEXT}, headers=auth)
    inv = client.get(f"/api/v1/investigations/{r.json()['id']}", headers=auth).json()
    assert inv["status"] == "COMPLETED"
    assert overlapped == [True]
    stages = [e["stage"] for e in inv["timeline"]]
    assert stages.index("FEATURE_EXTRACTION") < stages.index("EVIDENCE_RETRIEVAL"), "timeline order is unchanged"


def test_a_url_engine_failure_does_not_wait_for_slow_retrieval(client, auth, monkeypatch):
    def url_run(self, ctx, result):
        raise RuntimeError("boom")

    def ev_run(self, ctx, result):
        time.sleep(3)

    monkeypatch.setattr(UrlEngine, "run", lambda self, ctx: url_run(self, ctx, None))
    monkeypatch.setattr(EvidenceEngine, "_run", ev_run)
    started = time.perf_counter()
    r = client.post("/api/v1/investigations", json={"type": "text", "content": TEXT + " x"}, headers=auth)
    elapsed = time.perf_counter() - started
    inv = client.get(f"/api/v1/investigations/{r.json()['id']}", headers=auth).json()
    assert inv["status"] == "FAILED"
    assert elapsed < 2.5, f"the failure waited for retrieval ({elapsed:.1f}s)"
