"""The report answers the reader's questions and keeps kinds of finding apart."""

from tests.test_v2_email_auth import FORGED
from tests.test_v2_reviews import SCAM, investigate


def report_of(client, auth, content, kind="message"):
    r = client.post("/api/v1/investigations", json={"type": kind, "content": content}, headers=auth)
    return client.get(f"/api/v1/investigations/{r.json()['id']}", headers=auth).json()


def test_scam_report_answers_every_question(client, auth):
    inv = investigate(client, auth, SCAM)
    rep = inv["result"]["report"]
    assert set(rep) >= {"what_was_analysed", "what_was_detected", "why", "findings", "evidence",
                        "reliability", "checks", "not_verified", "next_steps"}
    assert rep["why"]["score"] == inv["risk_score"] and rep["why"]["score_represents"]
    assert sum(d["points"] for d in rep["why"]["drivers"]) <= inv["risk_score"]
    assert rep["reliability"]["statement"].startswith(f"Risk {inv['risk_level']}")
    assert rep["next_steps"]["headline"] and rep["next_steps"]["urgency"]


def test_findings_are_labelled_by_how_they_are_known(client, auth):
    inv = investigate(client, auth, SCAM)
    kinds = {f["kind"] for f in inv["result"]["report"]["findings"]}
    assert "CONFIRMED_OBSERVATION" in kinds and "HEURISTIC_INDICATOR" in kinds
    assert "LLM_INTERPRETATION" not in kinds, "no model is configured, so nothing may be labelled as its output"
    heuristics = [f for f in inv["result"]["report"]["findings"] if f["kind"] == "HEURISTIC_INDICATOR"]
    assert all(f["limitation"] for f in heuristics)


def test_checks_say_what_was_and_was_not_done(client, auth):
    inv = investigate(client, auth, SCAM)
    checks = {c["check"]: c for c in inv["result"]["report"]["checks"]}
    assert checks["Link structure and lookalike-domain analysis"]["status"] == "completed"
    rep = checks["Threat-intelligence reputation lookup"]
    assert rep["status"] == "not_completed"
    assert checks["Domain registration age (WHOIS/RDAP)"]["status"] == "not_completed"
    assert checks["Linked page retrieved and inspected"]["status"] == "not_completed"
    assert inv["result"]["report"]["checks_not_completed"] >= 3


def test_no_listing_is_never_called_safe(client, auth, tmp_path, monkeypatch):
    from truthshield.settings import get_settings

    feed = tmp_path / "feed.txt"
    feed.write_text("some-other-domain.top\n", encoding="utf-8")
    monkeypatch.setattr(get_settings(), "THREAT_FEED_PATHS", str(feed))
    inv = investigate(client, auth, SCAM)
    check = next(c for c in inv["result"]["report"]["checks"] if c["check"].startswith("Threat-intelligence"))
    assert check["status"] == "completed" and "not thereby safe" in check["detail"]


def test_email_report_records_authentication_as_an_observation(client, auth):
    inv = report_of(client, auth, FORGED, kind="email")
    rep = inv["result"]["report"]
    assert any("DMARC=fail" in f["text"] for f in rep["findings"] if f["kind"] == "CONFIRMED_OBSERVATION")
    assert any(c["check"].startswith("Sender authentication") and c["status"] == "completed" for c in rep["checks"])


def test_benign_report_does_not_invent_drivers(client, auth):
    inv = investigate(client, auth, "Reached home safely, the train was an hour late. Talk tomorrow.")
    rep = inv["result"]["report"]
    assert rep["why"]["drivers"] == []
    # Known gap: a sentence with an implied "I" ("Reached home safely ...") is still typed
    # FACTUAL and searched. The report must show it as undecided, never as a finding.
    assert all(e["assessment"] in ("INSUFFICIENT_EVIDENCE", "NOT_CHECKED") for e in rep["evidence"])
