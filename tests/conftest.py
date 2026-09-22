"""
Shared fixtures.

Every test runs against a real (SQLite) database and a real FastAPI app —
no mocking of the layers under test. The only thing stubbed is the network,
because evidence retrieval is the one part whose behaviour depends on what
the web returns this minute.
"""

import os
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Must be set before truthshield.settings is imported anywhere.
os.environ.update({
    "APP_ENV": "test",
    "JWT_SECRET_KEY": "test-secret-key-that-is-long-enough-to-pass-validation",
    "DATABASE_URL": "sqlite:///./truthshield_test_v2.db",
    "CELERY_TASK_ALWAYS_EAGER": "true",
    "CORS_ORIGINS": "http://localhost:5173",
    "REDIS_URL": "redis://127.0.0.1:1",      # intentionally dead: exercises the cache fallback
})


@pytest.fixture(scope="session", autouse=True)
def _schema():
    from truthshield.infra.database import Base, engine
    import truthshield.infra.models  # noqa: F401  — registers the tables
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def session():
    from truthshield.infra.database import SessionLocal
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from truthshield.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def user_token(client):
    """A registered user's bearer token, with a unique address per test."""
    email = f"u{uuid.uuid4().hex[:10]}@example.com"
    response = client.post("/api/v1/auth/signup", json={
        "email": email, "password": "correct-horse-42",
    })
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


@pytest.fixture
def auth(user_token):
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture
def fixture_claims():
    """The frozen evidence set used to score verdict accuracy."""
    import json
    path = ROOT / "tests" / "fixtures" / "evidence_fixture.json"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["claims"]
