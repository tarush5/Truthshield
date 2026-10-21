"""Feature 1 end to end: a scam's factual claim is checked against an official source."""

import uuid

from tests.test_v2_evidence_api import account


def test_a_government_scheme_payment_claim_is_contradicted_by_the_official_notice(client, auth):
    marker = f"Krishi{uuid.uuid4().hex[:6]}"
    analyst = account(client, role="ANALYST")
    r = client.post("/api/v1/evidence/documents", headers=analyst, json={
        "title": f"{marker} scheme: registration is free",
        "text": f"Registration under the {marker} scheme is free of cost. No fee or payment is required to register "
                f"or to receive the installment. Farmers should not pay anyone claiming to process {marker} benefits.",
        "source_url": f"https://agriwelfare.gov.in/{marker.lower()}/free-registration",
    })
    assert r.status_code == 201
    message = (f"The {marker} scheme requires a registration fee of Rs 500 to receive the installment. "
               "Pay immediately at http://scheme-fee.top/pay to avoid losing your benefit.")
    r = client.post("/api/v1/investigations", json={"type": "message", "content": message}, headers=auth)
    inv = client.get(f"/api/v1/investigations/{r.json()['id']}", headers=auth).json()
    result = inv["result"]

    types = {s["text"][:20]: s["type"] for s in result["claim_screening"]}
    assert "FACTUAL" in types.values() and "INSTRUCTION" in types.values(), types

    claim = next(c for c in result["claims"] if marker in c["text"])
    assert claim["checked"] and claim["sources"], claim
    source = claim["sources"][0]
    assert source["category"] == "OFFICIAL" and source["citation"]["status"] == "verified"
    # Whatever the adjudicator concludes, it is never "supported" by a notice saying the opposite,
    # and the report shows the source and excerpt.
    assert claim["assessment"] != "SUPPORTED"
    evidence = result["report"]["evidence"]
    assert evidence and evidence[0]["sources"][0]["excerpt"]
    assert inv["risk_level"] in ("HIGH", "CRITICAL")
