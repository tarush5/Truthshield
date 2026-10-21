"""Scam-pattern trends and risk-aware urgency -- through the real app."""

import uuid
from datetime import datetime, timedelta, timezone

SCAM = ("Congratulations! You have won Rs 50,000. Click this link to claim your reward: "
        "http://reward-claim-sbi.top/verify")


def account(client):
    email = f"p{uuid.uuid4().hex[:10]}@example.com"
    body = client.post("/api/v1/auth/signup", json={"email": email, "password": "correct-horse-42"}).json()
    return {"Authorization": f"Bearer {body['access_token']}"}


def investigate(client, headers, content):
    r = client.post("/api/v1/investigations", json={"type": "message", "content": content}, headers=headers)
    return client.get(f"/api/v1/investigations/{r.json()['id']}", headers=headers).json()


def test_patterns_compare_windows_for_the_callers_own_investigations(client):
    me = account(client)
    old = investigate(client, me, SCAM + " [old]")
    investigate(client, me, SCAM + " [new 1]")
    investigate(client, me, SCAM + " [new 2]")

    # Move one investigation into the previous window.
    from truthshield.infra.database import SessionLocal
    from truthshield.infra.models import Investigation
    s = SessionLocal()
    s.get(Investigation, uuid.UUID(old["id"])).created_at = datetime.now(timezone.utc) - timedelta(days=10)
    s.commit()
    s.close()

    report = client.get("/api/v1/dashboard/patterns?days=7", headers=me).json()
    assert report["scope"] == "own"
    classes = {r["key"]: r for r in report["classifications"]}
    row = classes[old["classification"]]
    assert (row["current"], row["previous"], row["change"]) == (2, 1, 1.0)
    factor = next(r for r in report["risk_factors"] if r["key"] == old["risk_factors"][0]["code"])
    assert factor["current"] == 2 and factor["previous"] == 1 and factor["title"]

    # Another user sees none of it.
    other = client.get("/api/v1/dashboard/patterns?days=7", headers=account(client)).json()
    assert other["risk_factors"] == [] and other["classifications"] == []


def test_recommended_actions_carry_urgency_from_the_level(client):
    me = account(client)
    scam = investigate(client, me, SCAM)
    actions = scam["result"]["recommended_actions"]
    expected = "act_now" if scam["risk_level"] in ("HIGH", "CRITICAL") else "verify_first"
    assert actions["urgency"] == expected and actions["urgency_note"]

    benign = investigate(client, me, "Lunch is at 1:30 on Thursday in the usual place.")
    assert benign["result"]["recommended_actions"]["urgency"] == "stay_alert"
    # The shared action tables were copied, not modified.
    from truthshield.investigations.explain import GENERAL_ACTIONS
    assert "urgency" not in GENERAL_ACTIONS
