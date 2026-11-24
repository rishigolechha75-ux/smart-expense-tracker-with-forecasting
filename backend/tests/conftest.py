import os
import tempfile

# Configure a throwaway database before the app is imported.
_tmp = tempfile.mkdtemp()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key-that-is-at-least-32-bytes")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_user(client):
    """Register a fresh user and return (auth headers, user json)."""
    counter = {"n": 0}

    def _make(name="Test User"):
        counter["n"] += 1
        email = f"user{counter['n']}-{os.urandom(4).hex()}@example.com"
        r = client.post("/api/auth/register", json={"name": name, "email": email, "password": "s3cure-pass"})
        assert r.status_code == 201, r.text
        body = r.json()
        return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]

    return _make
