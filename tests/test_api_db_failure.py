"""Midterm T10: the database becomes unreachable during a request.

The expected behaviour, from the midterm test plan: "System handles the
failure gracefully, returning an appropriate error rather than crashing."
Concretely that means a 503 with a JSON message the frontend can show, and
no orphaned image files left on disk by the half-finished prediction.

The outage is simulated by pointing the request's database session at a port
nothing listens on, via FastAPI's dependency-override mechanism -- the same
code path a real outage takes (the driver raises OperationalError).
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.session import get_db
from conftest import MEDIA_DIR, sample_bytes, upload

DEAD_URL = "postgresql+psycopg2://visioret:visioret@127.0.0.1:1/visioret"


@pytest.fixture
def broken_db_client(app, client):  # `client` first, so the model is already loaded
    engine = create_engine(DEAD_URL, connect_args={"connect_timeout": 2})
    BrokenSession = sessionmaker(bind=engine)

    def broken_get_db():
        s = BrokenSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = broken_get_db
    # raise_server_exceptions=False: observe what a real HTTP client would get.
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


def test_predict_during_db_outage_returns_503_json(broken_db_client):
    files_before = set(os.listdir(MEDIA_DIR))
    r = upload(broken_db_client, sample_bytes("CNV"))
    assert r.status_code == 503
    assert "database" in r.json()["detail"].lower()
    # The two JPEGs written before the failed commit must have been removed.
    assert set(os.listdir(MEDIA_DIR)) == files_before


def test_history_during_db_outage_returns_503_json(broken_db_client):
    r = broken_db_client.get("/api/scans", headers={"X-Anon-Session": "abc"})
    assert r.status_code == 503
    assert "database" in r.json()["detail"].lower()


def test_health_still_answers_during_db_outage(broken_db_client):
    # Health reports the model, which does not depend on the database.
    assert broken_db_client.get("/api/health").status_code == 200
