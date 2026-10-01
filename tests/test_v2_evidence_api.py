"""
Evidence store API, source registry and claim search -- through the real app.
"""

import uuid

import pytest

PASSWORD = "correct-horse-42"


def account(client, monkeypatch=None, role=None):
    email = f"e{uuid.uuid4().hex[:10]}@example.com"
    body = client.post("/api/v1/auth/signup", json={"email": email, "password": PASSWORD}).json()
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    if role:
        from truthshield.infra.database import SessionLocal
        from truthshield.infra.models import User
        s = SessionLocal()
        user = s.get(User, uuid.UUID(body["user"]["id"]))
        user.role = role
        s.commit()
        s.close()
    return headers


@pytest.fixture
def analyst(client):
    return account(client, role="ANALYST")


@pytest.fixture
def admin(client):
    return account(client, role="ADMIN")


def ingest(client, headers, marker, text=None, url=None):
    return client.post("/api/v1/evidence/documents", headers=headers, json={
        "title": f"{marker} advisory",
        "text": text or f"The {marker} health advisory states that lemon water does not cure cancer. "
                        "Oncologists recommend evidence-based treatment.",
        "source_url": url or f"https://www.who.int/news/{marker}",
    })


class TestIngestion:
    def test_regular_users_cannot_ingest(self, client, auth):
        r = ingest(client, auth, "nope")
        assert r.status_code == 403

    def test_analyst_ingests_text_and_it_is_searchable(self, client, analyst, auth):
        marker = f"m{uuid.uuid4().hex[:8]}"
        r = ingest(client, analyst, marker)
        assert r.status_code == 201 and r.json()["created"] and r.json()["chunks"] >= 1
        assert r.json()["source"]["domain"] == "who.int" and r.json()["source"]["category"] == "OFFICIAL"

        found = client.get(f"/api/v1/evidence/search?q={marker} lemon water cancer", headers=auth).json()
        top = found["results"][0]
        assert marker in top["passage"] and top["publisher"] == "who.int"
        assert set(top["scores"]["components"]) >= {"relevance", "keyword", "credibility"}
        assert found["embedding"]["kind"] in ("lexical", "semantic")

        doc = client.get(f"/api/v1/evidence/{top['document_id']}", headers=auth).json()
        assert doc["content_scope"] == "uploaded" and doc["chunks"] and "embedding" not in doc["chunks"][0]

    def test_same_document_twice_is_not_duplicated(self, client, analyst):
        marker = f"d{uuid.uuid4().hex[:8]}"
        assert ingest(client, analyst, marker).json()["created"]
        assert not ingest(client, analyst, marker).json()["created"]

    def test_text_needs_a_citable_source(self, client, analyst):
        r = client.post("/api/v1/evidence/documents", headers=analyst, json={"text": "x" * 100})
        assert r.status_code == 422

    def test_url_ingestion_goes_through_the_ssrf_guard(self, client, analyst):
        r = client.post("/api/v1/evidence/documents", headers=analyst, json={"url": "http://127.0.0.1:8000/admin"})
        assert r.status_code == 400 and r.json()["error"]["code"] == "BLOCKED_URL"

    def test_ingestion_is_audited(self, client, analyst, session):
        from truthshield.infra.models import AuditLog
        ingest(client, analyst, f"a{uuid.uuid4().hex[:8]}")
        assert session.query(AuditLog).filter(AuditLog.action == "evidence.ingest").count() >= 1


class TestSearchFilters:
    def test_category_filter_and_validation(self, client, analyst, auth):
        marker = f"f{uuid.uuid4().hex[:8]}"
        ingest(client, analyst, marker)
        ingest(client, analyst, marker, text=f"{marker} rumours spread on forums that lemon water cures cancer.",
               url=f"https://www.reddit.com/r/x/{marker}")
        official = client.get(f"/api/v1/evidence/search?q={marker} lemon&category=OFFICIAL", headers=auth).json()
        assert official["results"] and all(r["category"] == "OFFICIAL" for r in official["results"])
        assert client.get("/api/v1/evidence/search?q=x y&category=NONSENSE", headers=auth).status_code == 400

    def test_unknown_document(self, client, auth):
        assert client.get(f"/api/v1/evidence/{uuid.uuid4()}", headers=auth).status_code == 404


class TestSources:
    def test_list_and_curate(self, client, analyst, admin, auth, session):
        from truthshield.infra.models import AuditLog
        marker = f"s{uuid.uuid4().hex[:8]}"
        ingest(client, analyst, marker, url=f"https://{marker}-news.example/story")
        listed = client.get(f"/api/v1/sources?q={marker}", headers=auth).json()
        source = listed["items"][0]
        assert source["domain"] == f"{marker}-news.example" and not source["curated"]

        assert client.patch(f"/api/v1/sources/{source['id']}", json={"category": "SECONDARY"}, headers=auth).status_code == 403
        r = client.patch(f"/api/v1/sources/{source['id']}", headers=admin,
                         json={"category": "SECONDARY", "credibility": 0.82, "notes": "Established outlet"})
        assert r.status_code == 200 and r.json()["curated"] and r.json()["credibility"] == 0.82
        assert session.query(AuditLog).filter(AuditLog.action == "source.update").count() >= 1


class TestClaimSearch:
    def test_claims_are_scoped_to_their_owner(self, client, auth):
        text = "The Reserve Bank of India raised the repo rate by fifty basis points in August 2025."
        client.post("/api/v1/investigations", json={"type": "text", "content": text}, headers=auth)
        mine = client.get("/api/v1/claims?q=repo rate", headers=auth).json()["items"]
        assert mine and "repo rate" in mine[0]["text"] and mine[0]["public_id"].startswith("TS-")
        stranger = account(client)
        assert client.get("/api/v1/claims?q=repo rate", headers=stranger).json()["items"] == []


class TestHealth:
    def test_health_reports_providers_and_store(self, client):
        body = client.get("/api/v1/system/health").json()
        assert body["providers"]["llm"]["available"] is False
        assert body["providers"]["ocr"]["provider"] in ("none", "tesseract")
        assert body["evidence_store"]["backend"].startswith("in-process")
